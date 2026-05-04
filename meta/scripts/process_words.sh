#!/bin/bash
# Process up to 20 words from phase_1_words.txt

count=0
max=20

while [ "$count" -lt "$max" ]; do
  word=$(head -1 training_data/phases/phase_1_words.txt 2>/dev/null)
  [ -z "$word" ] && break
  
  # Determine last file number
  lastfile=$(ls training_data/phases/phase_1/ | sort -t_ -k3 -n | tail -1)
  lastnum=$(echo "$lastfile" | sed 's/phase_1_//;s/\.md//')
  nextnum=$((lastnum + 1))
  nextnum=$(printf "%03d" "$nextnum")
  filename="phase_1_${nextnum}.md"
  filepath="training_data/phases/phase_1/${filename}"
  
  echo "Processing: $word -> $filename"
  
  # Generate file content based on word
  case "$word" in
    needle)
      cat > "$filepath" << 'FILEEOF'
[user]what does a needle look like?
[Ninereeds]This is a needle.
A needle is thin.
A needle is long.
A needle is sharp.
A needle is pointed.
A needle is made of metal.
A needle is a thin sharp piece of metal.

[user]where is a needle?
[Ninereeds]This is a needle.
A needle is in a sewing box.
A needle is on a table.
A needle is in a cushion.
A needle is in a hand.
A needle is in a sewing kit.
A needle is a tool in a sewing kit.

[user]what does a needle do?
[Ninereeds]This is a needle.
A needle pokes holes in cloth.
A needle pulls thread through fabric.
A needle goes in and out.
A needle follows a line.
A needle pierces material.
A needle pokes holes and pulls thread.

[user]what is a needle for?
[Ninereeds]This is a needle.
A needle sews pieces of cloth.
A needle joins fabric together.
A needle mends a tear.
A needle makes clothes.
A needle makes stitches.
A needle sews cloth into clothes.
FILEEOF
      ;;
    net)
      cat > "$filepath" << 'FILEEOF'
[user]what does a net look like?
[Ninereeds]This is a net.
A net has holes.
A net is made of string.
A net is like a web.
A net is loose.
A net has a mesh.
A net is a web of string with holes.

[user]where is a net?
[Ninereeds]This is a net.
A net is in a pond.
A net is in a field.
A net is on a pole.
A net is in a goal.
A net is near water.
A net is a tool near water.

[user]what does a net do?
[Ninereeds]This is a net.
A net catches fish.
A net catches butterflies.
A net holds things in place.
A net stops a ball.
A net scoops up items.
A net catches fish and butterflies.

[user]what is a net for?
[Ninereeds]This is a net.
A net catches food from water.
A net gathers leaves.
A net protects a garden.
A net keeps bugs away.
A net collects falling fruit.
A net catches food and protects plants.
FILEEOF
      ;;
    newt)
      cat > "$filepath" << 'FILEEOF'
[user]what does a newt look like?
[Ninereeds]This is a newt.
A newt is small.
A newt has four legs.
A newt has a long tail.
A newt has smooth skin.
A newt is a kind of lizard.
A newt is a small animal with a tail.

[user]where is a newt?
[Ninereeds]This is a newt.
A newt is in a pond.
A newt is under a rock.
A newt is near water.
A newt is on wet ground.
A newt is in a damp place.
A newt is a creature near water.

[user]what does a newt do?
[Ninereeds]This is a newt.
A newt swims in the pond.
A newt walks on land.
A newt hunts for bugs.
A newt hides under rocks.
A newt eats small insects.
A newt swims and hunts for bugs.

[user]what is a newt for?
[Ninereeds]This is a newt.
A newt lives in a tank.
A newt is a pet for people.
A newt eats mosquitoes.
A newt keeps bug numbers down.
A newt is part of nature.
A newt is a pet and a bug eater.
FILEEOF
      ;;
    nickel)
      cat > "$filepath" << 'FILEEOF'
[user]what does a nickel look like?
[Ninereeds]This is a nickel.
A nickel is round.
A nickel is silver.
A nickel is a coin.
A nickel is flat.
A nickel has a picture on one side.
A nickel is a round silver coin.

[user]where is a nickel?
[Ninereeds]This is a nickel.
A nickel is in a pocket.
A nickel is in a purse.
A nickel is on a table.
A nickel is in a cash register.
A nickel is in a wallet.
A nickel is a coin in a pocket.

[user]what does a nickel do?
[Ninereeds]This is a nickel.
A nickel buys things.
A nickel is money.
A nickel is worth five cents.
A nickel pays for small items.
A nickel trades for goods.
A nickel is money that buys things.

[user]what is a nickel for?
[Ninereeds]This is a nickel.
A nickel pays for candy.
A nickel buys a gumball.
A nickel buys a pencil.
A nickel buys a stamp.
A nickel pays for a newspaper.
A nickel is money for small purchases.
FILEEOF
      ;;
    noise)
      cat > "$filepath" << 'FILEEOF'
[user]what does noise sound like?
[Ninereeds]This is noise.
Noise is loud.
Noise is sound.
Noise can be soft.
Noise can be harsh.
Noise fills the air.
Noise is loud sound in the air.

[user]where is noise?
[Ninereeds]This is noise.
Noise is on a busy street.
Noise is in a city.
Noise is in a room.
Noise is at a party.
Noise is near a machine.
Noise is sound in a busy place.

[user]what does noise do?
[Ninereeds]This is noise.
Noise comes from cars.
Noise comes from people talking.
Noise comes from machines.
Noise comes from music.
Noise travels through the air.
Noise comes from cars and people.

[user]what is noise for?
[Ninereeds]This is noise.
Noise warns of danger.
Noise signals a problem.
Noise gets attention.
Noice makes people look up.
Noise alerts a person.
Noise warns and alerts people.
FILEEOF
      ;;
    noodle)
      cat > "$filepath" << 'FILEEOF'
[user]what does a noodle look like?
[Ninereeds]This is a noodle.
A noodle is long.
A noodle is thin.
A noodle is soft when cooked.
A noodle is straight.
A noodle is made from dough.
A noodle is a long thin piece of dough.

[user]where is a noodle?
[Ninereeds]This is a noodle.
A noodle is in a bowl.
A noodle is in a pot.
A noodle is on a plate.
A noodle is in soup.
A noodle is in a box.
A noodle is food in a bowl.

[user]what does a noodle do?
[Ninereeds]This is a noodle.
A noodle gets cooked in water.
A noodle gets soft in hot water.
A noodle slides around on a plate.
A noodle soaks up sauce.
A noodle fills a bowl.
A noodle gets soft and soaks up sauce.

[user]what is a noodle for?
[Ninereeds]This is a noodle.
A noodle is food for people.
A noodle fills an empty tummy.
A noodle is eaten for lunch.
A noodle is eaten for dinner.
A noodle gives energy.
A noodle is food that fills a tummy.
FILEEOF
      ;;
    nose)
      cat > "$filepath" << 'FILEEOF'
[user]what does a nose look like?
[Ninereeds]This is a nose.
A nose is on a face.
A nose has two holes.
A nose sticks out from the face.
A nose is in the middle of the face.
A nose can be small or big.
A nose is a part of the face.

[user]where is a nose?
[Ninereeds]This is a nose.
A nose is between the eyes.
A nose is above the mouth.
A nose is below the forehead.
A nose is on the front of the head.
A nose is in the center of the face.
A nose is between the eyes and the mouth.

[user]what does a nose do?
[Ninereeds]This is a nose.
A nose smells flowers.
A nose breathes air.
A nose takes in air.
A nose senses odors.
A nose picks up scents.
A nose smells and breathes air.

[user]what is a nose for?
[Ninereeds]This is a nose.
A nose smells food.
A nose smells smoke in a fire.
A nose helps a person breathe.
A nose warms the air.
A nose filters dust from air.
A nose smells food and helps a person breathe.
FILEEOF
      ;;
    nut)
      cat > "$filepath" << 'FILEEOF'
[user]what does a nut look like?
[Ninereeds]This is a nut.
A nut is small.
A nut has a hard shell.
A nut is brown.
A nut is round or oval.
A nut has a seed inside.
A nut is a small brown food with a shell.

[user]where is a nut?
[Ninereeds]This is a nut.
A nut is on a tree.
A nut is on the ground.
A nut is in a bowl.
A nut is in a bag.
A nut is in a shell.
A nut is on a tree or on the ground.

[user]what does a nut do?
[Ninereeds]This is a nut.
A nut falls from a tree.
A nut cracks open.
A nut holds a seed inside.
A nut grows on a branch.
A nut ripens in the sun.
A nut cracks open to show a seed.

[user]what is a nut for?
[Ninereeds]This is a nut.
A nut is food for squirrels.
A nut is food for birds.
A nut is a snack for people.
A nut grows into a new tree.
A nut feeds animals in the wild.
A nut is food for squirrels and birds.
FILEEOF
      ;;
    oak)
      cat > "$filepath" << 'FILEEOF'
[user]what does an oak look like?
[Ninereeds]This is an oak.
An oak is a tree.
An oak is tall.
An oak has a thick trunk.
An oak has many branches.
An oak has green leaves.
An oak is a tall tree with a thick trunk.

[user]where is an oak?
[Ninereeds]This is an oak.
An oak is in a forest.
An oak is in a park.
An oak is in a yard.
An oak is near a house.
An oak is on a hill.
An oak is a tree in a forest.

[user]what does an oak do?
[Ninereeds]This is an oak.
An oak grows leaves in spring.
An oak drops acorns in fall.
An oak gives shade in summer.
An oak grows tall over time.
An oak loses leaves in winter.
An oak gives shade and drops acorns.

[user]what is an oak for?
[Ninereeds]This is an oak.
An oak gives wood for furniture.
An oak is a home for birds.
An oak is a home for squirrels.
An oak makes the air clean.
An oak gives shade on a hot day.
An oak gives wood and a home for birds.
FILEEOF
      ;;
    oar)
      cat > "$filepath" << 'FILEEOF'
[user]what does an oar look like?
[Ninereeds]This is an oar.
An oar is long.
An oar is made of wood.
An oar has a flat end.
An oar has a handle.
An oar is straight.
An oar is a long stick with a flat end.

[user]where is an oar?
[Ninereeds]This is an oar.
An oar is in a boat.
An oar is on a dock.
An oar is in a hand.
An oar is on a shelf.
An oar is near the water.
An oar is a tool in a boat.

[user]what does an oar do?
[Ninereeds]This is an oar.
An oar pushes against water.
An oar moves a boat forward.
An oar steers a boat.
An oar dips into water.
An oar pulls through water.
An oar pushes water to move a boat.

[user]what is an oar for?
[Ninereeds]This is an oar.
An oar rows a boat across a lake.
An oar moves a boat on a river.
An oar helps a person travel on water.
An oar propels a canoe.
An oar guides a raft.
An oar rows a boat across water.
FILEEOF
      ;;
    oat)
      cat > "$filepath" << 'FILEEOF'
[user]what does an oat look like?
[Ninereeds]This is an oat.
An oat is small.
An oat is a grain.
An oat is beige.
An oat is oval.
An oat grows on a stalk.
An oat is a small beige grain.

[user]where is an oat?
[Ninereeds]This is an oat.
An oat is in a field.
An oat is on a stalk.
An oat is in a bowl.
An oat is in a bag.
An oat is in a box.
An oat is a grain in a field.

[user]what does an oat do?
[Ninereeds]This is an oat.
An oat grows in the sun.
An oat gets harvested in summer.
An oat gets ground into flour.
An oat gets rolled into flakes.
An oat gets cooked into porridge.
An oat gets harvested and cooked into food.

[user]what is an oat for?
[Ninereeds]This is an oat.
An oat is food for people.
An oat makes oatmeal.
An oat makes granola bars.
An oat is food for horses.
An oat is a healthy breakfast.
An oat is food for people and horses.
FILEEOF
      ;;
    ocean)
      cat > "$filepath" << 'FILEEOF'
[user]what does the ocean look like?
[Ninereeds]This is the ocean.
The ocean is blue.
The ocean is wide.
The ocean is deep.
The ocean goes far to the sky.
The ocean has waves.
The ocean is a wide blue body of water.

[user]where is the ocean?
[Ninereeds]This is the ocean.
The ocean is next to land.
The ocean is at the beach.
The ocean is around islands.
The ocean is at the edge of the world.
The ocean is under the sky.
The ocean is the water next to land.

[user]what does the ocean do?
[Ninereeds]This is the ocean.
The ocean has waves that crash on shore.
The ocean moves up and down.
The ocean flows with the tides.
The ocean swirls in currents.
The ocean changes with the moon.
The ocean has waves that crash and flow.

[user]what is the ocean for?
[Ninereeds]This is the ocean.
The ocean is home for fish.
The ocean is home for whales.
The ocean holds many creatures.
The ocean gives us food.
The ocean is a place for boats.
The ocean is home for fish and whales.
FILEEOF
      ;;
    octopus)
      cat > "$filepath" << 'FILEEOF'
[user]what does an octopus look like?
[Ninereeds]This is an octopus.
An octopus has eight arms.
An octopus has a round body.
An octopus is soft.
An octopus has suckers on the arms.
An octopus lives in the sea.
An octopus is a soft sea animal with eight arms.

[user]where is an octopus?
[Ninereeds]This is an octopus.
An octopus is in the ocean.
An octopus is in a cave.
An octopus is under a rock.
An octopus is in a coral reef.
An octopus is in deep water.
An octopus is a sea animal in the ocean.

[user]what does an octopus do?
[Ninereeds]This is an octopus.
An octopus swims in water.
An octopus crawls on the sea floor.
An octopus hides from predators.
An octopus squirts ink to escape.
An octopus changes color to blend in.
An octopus swims and hides from danger.

[user]what is an octopus for?
[Ninereeds]This is an octopus.
An octopus hunts for crabs.
An octopus hunts for fish.
An octopus is food for sharks.
An octopus is food for whales.
An octopus is part of the ocean food chain.
An octopus hunts crabs and feeds sharks.
FILEEOF
      ;;
    odor)
      cat > "$filepath" << 'FILEEOF'
[user]what does an odor smell like?
[Ninereeds]This is an odor.
An odor is a smell.
An odor is in the air.
An odor can be sweet.
An odor can be strong.
An odor can be bad.
An odor is a smell that floats in the air.

[user]where is an odor?
[Ninereeds]This is an odor.
An odor is in a room.
An odor is in a kitchen.
An odor is outside.
An odor comes from a source.
An odor is in a place.
An odor is a smell in a room.

[user]what does an odor do?
[Ninereeds]This is an odor.
An odor travels through the air.
An odor fills a space.
An odor reaches the nose.
An odor spreads from one place to another.
An odor lingers in the air.
An odor travels through air to the nose.

[user]what is an odor for?
[Ninereeds]This is an odor.
An odor tells about food.
An odor warns of smoke.
An odor signals ripe fruit.
An odor signals spoiled milk.
An odor gives information about a thing.
An odor tells about food and warns of danger.
FILEEOF
      ;;
    oil)
      cat > "$filepath" << 'FILEEOF'
[user]what does oil look like?
[Ninereeds]This is oil.
Oil is slippery.
Oil is thick.
Oil is shiny on water.
Oil is yellow or clear.
Oil is a liquid.
Oil is a slippery thick liquid.

[user]where is oil?
[Ninereeds]This is oil.
Oil is in a bottle.
Oil is in a pan.
Oil is in a car.
Oil is in the ground.
Oil is in a machine.
Oil is a liquid in a bottle or a car.

[user]what does oil do?
[Ninereeds]This is oil.
Oil makes things slide.
Oil covers a surface.
Oil coats a pan.
Oil floats on water.
Oil keeps a machine running.
Oil makes things slide and keeps machines running.

[user]what is oil for?
[Ninereeds]This is oil.
Oil cooks food in a pan.
Oil makes a car engine run.
Oil lubricates moving parts.
Oil stops rust on metal.
Oil is fuel for heat.
Oil cooks food and runs car engines.
FILEEOF
      ;;
    ointment)
      cat > "$filepath" << 'FILEEOF'
[user]what does ointment look like?
[Ninereeds]This is ointment.
Ointment is thick.
Ointment is smooth.
Ointment is in a tube.
Ointment is in a jar.
Ointment is greasy.
Ointment is a thick smooth cream in a tube.

[user]where is ointment?
[Ninereeds]This is ointment.
Ointment is on a shelf.
Ointment is in a bathroom.
Ointment is in a medicine cabinet.
Ointment is in a first aid kit.
Ointment is on the skin.
Ointment is a cream in a bathroom cabinet.

[user]what does ointment do?
[Ninereeds]This is ointment.
Ointment rubs into the skin.
Ointment covers a rash.
Ointment soothes a burn.
Ointment moisturizes dry skin.
Ointment stays on the skin.
Ointment rubs in and soothes the skin.

[user]what is ointment for?
[Ninereeds]This is ointment.
Ointment heals a cut.
Ointment soothes a bug bite.
Ointment treats a rash.
Ointment protects the skin.
Ointment stops itching.
Ointment heals cuts and soothes bug bites.
FILEEOF
      ;;
    onion)
      cat > "$filepath" << 'FILEEOF'
[user]what does an onion look like?
[Ninereeds]This is an onion.
An onion is round.
An onion has layers.
An onion is white.
An onion is purple sometimes.
An onion has papery skin.
An onion is a round vegetable with layers.

[user]where is an onion?
[Ninereeds]This is an onion.
An onion is in the ground.
An onion is in a kitchen.
An onion is on a shelf.
An onion is in a basket.
An onion is in a garden.
An onion is a vegetable in the ground.

[user]what does an onion do?
[Ninereeds]This is an onion.
An onion makes eyes water when cut.
An onion has a strong smell.
An onion grows underground.
An onion stores food in layers.
An onion sprouts green tops.
An onion makes eyes water and has a strong smell.

[user]what is an onion for?
[Ninereeds]This is an onion.
An onion adds flavor to food.
An onion is a vegetable for cooking.
An onion goes into soup.
An onion goes into a salad.
An onion is a base for many dishes.
An onion adds flavor to soup and salad.
FILEEOF
      ;;
    opener)
      cat > "$filepath" << 'FILEEOF'
[user]what does an opener look like?
[Ninereeds]This is an opener.
An opener is made of metal.
An opener has a curved end.
An opener has a handle.
An opener is small.
An opener has a sharp edge.
An opener is a small metal tool with a handle.

[user]where is an opener?
[Ninereeds]This is an opener.
An opener is in a drawer.
An opener is in a kitchen.
An opener is on a counter.
An opener is in a tool box.
An opener is near the sink.
An opener is a tool in a kitchen drawer.

[user]what does an opener do?
[Ninereeds]This is an opener.
An opener lifts a metal lid.
An opener cuts into a can top.
An opener grips a bottle cap.
An opener twists a lid off.
An opener pierces a seal.
An opener lifts lids and opens cans.

[user]what is an opener for?
[Ninereeds]This is an opener.
An opener opens cans of food.
An opener opens bottles of soda.
An opener opens jars of jam.
An opener helps access food.
An opener makes opening containers easy.
An opener opens cans and bottles of food.
FILEEOF
      ;;
    orchid)
      cat > "$filepath" << 'FILEEOF'
[user]what does an orchid look like?
[Ninereeds]This is an orchid.
An orchid is a flower.
An orchid has bright petals.
An orchid has a colorful center.
An orchid grows on a stem.
An orchid has three petals.
An orchid is a flower with bright petals.

[user]where is an orchid?
[Ninereeds]This is an orchid.
An orchid is in a pot.
An orchid is on a windowsill.
An orchid is in a greenhouse.
An orchid is in a garden.
An orchid is in a warm room.
An orchid is a flower in a pot.

[user]what does an orchid do?
[Ninereeds]This is an orchid.
An orchid blooms once a year.
An orchid opens its petals slowly.
An orchid stays in bloom for weeks.
An orchid reaches toward the light.
An orchid grows roots in bark.
An orchid blooms and stays in bloom for weeks.

[user]what is an orchid for?
[Ninereeds]This is an orchid.
An orchid decorates a room.
An orchid is a gift for a person.
An orchid is a pretty plant.
An orchid brightens a home.
An orchid is a decoration in a house.
An orchid decorates a room and brightens a home.
FILEEOF
      ;;
    organ)
      cat > "$filepath" << 'FILEEOF'
[user]what does an organ look like?
[Ninereeds]This is an organ.
An organ is inside the body.
An organ has a specific shape.
An organ is made of tissue.
An organ is soft.
An organ is a part of the body.
An organ is a soft part inside the body.

[user]where is an organ?
[Ninereeds]This is an organ.
An organ is in the chest.
An organ is in the belly.
An organ is inside a person.
An organ is inside an animal.
An organ is in a specific place in the body.
An organ is a body part in the chest or belly.

[user]what does an organ do?
[Ninereeds]This is an organ.
An organ does a job for the body.
An organ pumps blood.
An organ filters waste.
An organ digests food.
An organ helps the body work.
An organ pumps blood and digests food.

[user]what is an organ for?
[Ninereeds]This is an organ.
An organ keeps the body alive.
An organ moves blood through the body.
An organ cleans the blood.
An organ processes food into energy.
An organ sends signals through the body.
An organ keeps the body alive and working.
FILEEOF
      ;;
    *)
      echo "Unknown word: $word" >&2
      # Remove the word anyway to avoid infinite loop
      sed -i '1d' training_data/phases/phase_1_words.txt
      continue
      ;;
  esac
  
  # Step 4: Update dependency graph
  jq --arg f "$filepath" '.nodes[$f] = {"path": $f, "kind": "phase"}' training_data/dependency_graph.json > /tmp/dg_tmp.json && mv /tmp/dg_tmp.json training_data/dependency_graph.json
  
  # Step 5: Remove the processed word
  sed -i '1d' training_data/phases/phase_1_words.txt
  
  # Step 6: Append to ledger
  echo "$word -> $filepath" >> training_data/dependency_graph_progress.txt
  
  count=$((count + 1))
done

echo ""
echo "RECEIPT"
echo "Files written: $count"
echo "Last file: $filename"
echo "Remaining: $(wc -l < training_data/phases/phase_1_words.txt)"
