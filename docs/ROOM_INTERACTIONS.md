# Nindo_mud room interaction messages

Room occupants now see successful, observable actions by other players. These
are **same-room messages**, never global announcements.

| Action | What bystanders see |
| --- | --- |
| Eat food, holiday candy, or edible medicine | Player eats item |
| Drink | Player drinks item |
| Sleep, rest, stand, wake | Player lies down, rests, or stands |
| Drop/get one ground item | Player drops or picks up named item |
| Drop/get all | Single summarized count, not hundreds of lines |
| Get from backpack | Player takes item from their backpack |
| Drop/pick up Ryo | Player drops or collects a pile of Ryo |
| Give items or Ryo | Others see player hand something over; recipient already has their own notice |
| Wear, wield, remove equipment | Player puts on, wields, or removes an item |
| Train/practice | Player visibly trains or practices |
| Start a fight, land or miss an ordinary melee attack | Player-versus-mob and player-versus-player room messages |
| Mob strikes player | Room observers see resulting attacks |
| Hand signs | Nearby players see casting signs when they can see the caster |
| Offensive jutsu | Room observers see the technique used on an opponent (Silent Genjutsu stays secret) |
| Medical supplies | Using an item is visible when it is successfully consumed |
| Wear all/remove all | One aggregate equipment message for the room |
| Enter Camouflage | Nearby witnesses see the ninja fade from sight |
| Leave/break Camouflage | Nearby witnesses see the ninja reappear |

The actor already receives a private action confirmation and does not also
receive the room observation. PvP combat partners don't receive an additional
copy of hit messages.

## Stealth and privacy

The action emitter checks every room observer separately:
- Immortal `wizinvis` never discloses an action, even to Sensory Detect.
- Once Camouflage is active, ordinary players cannot see the user's further
  item, training, or combat observations. Sensory Detect can observe them.
- The *initial* fade into Camouflage is visible to people already present;
  later hidden actions are not.
- A player in another room never receives these messages. Clone scouting uses
  the recipient's actual view room.
- Failed or blocked commands do **not** create action notifications.
- Bulk get/drop sends one aggregate message, not one message per item.

The update is code-only. The release archive must not include or overwrite the
server's existing `data/` directory.
