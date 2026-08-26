from image_registry.unsplash_search import normalize


def test_normalize_preserves_required_unsplash_provenance():
    row = normalize(
        {
            "id": "photo-id",
            "description": None,
            "alt_description": "a test photograph",
            "width": 1200,
            "height": 800,
            "user": {
                "name": "Photographer",
                "username": "photographer",
                "links": {"html": "https://unsplash.com/@photographer"},
            },
            "links": {
                "html": "https://unsplash.com/photos/photo-id",
                "download_location": "https://api.unsplash.com/photos/photo-id/download",
            },
            "urls": {"full": "https://images.unsplash.com/full", "small": "https://images.unsplash.com/small"},
        },
        "test query",
    )

    assert row["source"] == "unsplash"
    assert row["source_id"] == "photo-id"
    assert row["author"] == "Photographer"
    assert row["download_location"].endswith("/download")
    assert row["hotlinked_image_urls"]["full"] == "https://images.unsplash.com/full"
    assert row["license_url"] == "https://unsplash.com/license"
