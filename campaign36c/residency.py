from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable

from .persistence import PackedCellStore


class ResidencyTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COOL = "cool"
    COLD = "cold"
    DORMANT = "dormant"


@dataclass
class ResidencyTelemetry:
    activations: int = 0
    page_loads: int = 0
    cache_hits: int = 0
    load_waits: int = 0
    bytes_read: int = 0
    useful_record_bytes: int = 0
    prefetched_uids: int = 0
    evictions: int = 0
    persistent_writes: int = 0
    peak_pending_pages: int = 0

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["useful_byte_ratio"] = (
            self.useful_record_bytes / self.bytes_read if self.bytes_read else 1.0
        )
        return value


@dataclass
class ResidentPage:
    segment_id: str
    tier: ResidencyTier = ResidencyTier.COLD
    records: tuple[dict[str, Any], ...] | None = None
    last_access: int = 0
    outstanding_io: bool = False
    requested_uids: set[int] = field(default_factory=set)


class GraphResidencyManager:
    """Graph-directed read-only page cache for sparse Campaign 36C tissue."""

    def __init__(
        self,
        store: PackedCellStore,
        *,
        maximum_hot_pages: int = 8,
        maximum_warm_pages: int = 32,
        maximum_cool_pages: int = 128,
    ) -> None:
        if min(maximum_hot_pages, maximum_warm_pages, maximum_cool_pages) <= 0:
            raise ValueError("residency capacities must be positive")
        self.store = store
        self.maximum_hot_pages = maximum_hot_pages
        self.maximum_warm_pages = maximum_warm_pages
        self.maximum_cool_pages = maximum_cool_pages
        self.telemetry = ResidencyTelemetry()
        self._clock = 0
        self._pending_uids: set[int] = set()
        self._lifecycle = {
            int(uid): str(value)
            for uid, value in store.manifest.get("lifecycle", {}).items()
        }
        active_segments = {
            location["segment_id"]
            for location in store.manifest["uid_index"].values()
        }
        self.pages = {
            segment_id: ResidentPage(segment_id)
            for segment_id in active_segments
        }
        self._segment_declarations = {
            item["segment_id"]: item for item in store.manifest["segments"]
            if item["segment_id"] in active_segments
        }

    @property
    def pending_uids(self) -> tuple[int, ...]:
        return tuple(sorted(self._pending_uids))

    @property
    def quiescent(self) -> bool:
        return not self._pending_uids and not any(
            page.outstanding_io for page in self.pages.values()
        )

    def tier_for_uid(self, uid: int) -> ResidencyTier:
        location = self.store.manifest["uid_index"].get(str(uid))
        if location is None:
            raise KeyError(f"unknown UID {uid}")
        if self._lifecycle.get(uid) == ResidencyTier.DORMANT.value:
            return ResidencyTier.DORMANT
        return self.pages[location["segment_id"]].tier

    def _routable(self, uid: int) -> bool:
        return self._lifecycle.get(uid, "admitted") != ResidencyTier.DORMANT.value

    def _halo(self, frontier: set[int], hops: int) -> set[int]:
        adjacency = self.store.manifest["adjacency"]
        visited = set(frontier)
        wave = set(frontier)
        for _ in range(hops):
            next_wave = {
                int(destination)
                for uid in wave
                for destination in adjacency.get(str(uid), [])
                if int(destination) not in visited and self._routable(int(destination))
            }
            visited.update(next_wave)
            wave = next_wave
            if not wave:
                break
        return visited

    def _load_page(
        self,
        segment_id: str,
        requested_uids: set[int],
    ) -> tuple[ResidentPage, bool]:
        page = self.pages[segment_id]
        page.requested_uids.update(requested_uids)
        page.last_access = self._clock
        if page.records is not None:
            self.telemetry.cache_hits += 1
            return page, False
        page.outstanding_io = True
        self.telemetry.peak_pending_pages = max(
            self.telemetry.peak_pending_pages,
            sum(item.outstanding_io for item in self.pages.values()),
        )
        # The UID is logically pending before this synchronous v0 load starts;
        # an asynchronous implementation can preserve the same invariant.
        self.telemetry.load_waits += 1
        page.records = self.store.load_segment(segment_id)
        declaration = self._segment_declarations[segment_id]
        self.telemetry.page_loads += 1
        self.telemetry.bytes_read += int(declaration["byte_size"])
        page.outstanding_io = False
        return page, True

    def _enforce_capacity(self, protected: set[str]) -> None:
        def demote(tier: ResidencyTier, limit: int, destination: ResidencyTier) -> None:
            members = sorted(
                (
                    page for page in self.pages.values()
                    if page.tier is tier and page.segment_id not in protected
                ),
                key=lambda page: page.last_access,
            )
            total = sum(page.tier is tier for page in self.pages.values())
            for page in members[: max(0, total - limit)]:
                page.tier = destination

        demote(ResidencyTier.HOT, self.maximum_hot_pages, ResidencyTier.WARM)
        demote(ResidencyTier.WARM, self.maximum_warm_pages, ResidencyTier.COOL)
        cool = sorted(
            (
                page for page in self.pages.values()
                if page.tier is ResidencyTier.COOL and page.segment_id not in protected
            ),
            key=lambda page: page.last_access,
        )
        total_cool = sum(page.tier is ResidencyTier.COOL for page in self.pages.values())
        for page in cool[: max(0, total_cool - self.maximum_cool_pages)]:
            page.tier = ResidencyTier.COLD
            page.records = None
            page.requested_uids.clear()
            self.telemetry.evictions += 1

    def activate(
        self,
        frontier_uids: int | Iterable[int],
        *,
        halo_hops: int = 1,
    ) -> dict[int, dict[str, Any]]:
        if halo_hops < 0:
            raise ValueError("halo_hops must be non-negative")
        frontier = (
            {frontier_uids}
            if isinstance(frontier_uids, int)
            else set(frontier_uids)
        )
        if not frontier:
            raise ValueError("at least one frontier UID is required")
        index = self.store.manifest["uid_index"]
        if any(str(uid) not in index for uid in frontier):
            raise KeyError("frontier contains an unknown UID")
        if any(not self._routable(uid) for uid in frontier):
            raise RuntimeError("dormant tissue cannot enter the active frontier")
        halo = self._halo(frontier, halo_hops)
        self._pending_uids.update(halo)
        self.telemetry.activations += 1
        self.telemetry.prefetched_uids += len(halo.difference(frontier))
        self._clock += 1
        hot_segments = {index[str(uid)]["segment_id"] for uid in frontier}
        warm_segments = {
            index[str(uid)]["segment_id"] for uid in halo.difference(frontier)
        }
        requested_by_segment: dict[str, set[int]] = {}
        for uid in halo:
            requested_by_segment.setdefault(
                index[str(uid)]["segment_id"], set()
            ).add(uid)
        try:
            for segment_id, requested in requested_by_segment.items():
                page, loaded = self._load_page(segment_id, requested)
                page.tier = (
                    ResidencyTier.HOT
                    if segment_id in hot_segments
                    else ResidencyTier.WARM
                )
                if loaded:
                    self.telemetry.useful_record_bytes += sum(
                        int(index[str(uid)]["record_bytes"]) for uid in requested
                    )
            for page in self.pages.values():
                if page.segment_id not in requested_by_segment:
                    if page.tier is ResidencyTier.HOT:
                        page.tier = ResidencyTier.WARM
                    elif page.tier is ResidencyTier.WARM:
                        page.tier = ResidencyTier.COOL
            self._enforce_capacity(hot_segments | warm_segments)
            result: dict[int, dict[str, Any]] = {}
            for uid in frontier:
                location = index[str(uid)]
                page = self.pages[location["segment_id"]]
                if page.records is None:
                    raise RuntimeError("frontier page was evicted while active")
                record = page.records[int(location["record_index"])]
                if int(record["header"]["canonical_uid"]) != uid:
                    raise RuntimeError("resident UID index mismatch")
                result[uid] = record
            return result
        finally:
            self._pending_uids.difference_update(halo)

    def demote_all(self) -> None:
        if not self.quiescent:
            raise RuntimeError("cannot demote while page I/O is pending")
        for page in self.pages.values():
            page.tier = ResidencyTier.COLD
            page.records = None
            page.requested_uids.clear()

    def tiers(self) -> dict[str, int]:
        return {
            tier.value: sum(page.tier is tier for page in self.pages.values())
            for tier in ResidencyTier
        }
