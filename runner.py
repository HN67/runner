"""Sidescrolling runner game"""

# Import future annotations
from __future__ import annotations

# Import core modules
import os
import typing
import random
import itertools

# Import pygame
import pygame

# Define config
config = {
    "windowWidth": 512,
    "windowHeight": 512,
    "minimapWidth": 2048,
    "minimapHeight": 2048,
    "minimapScale": 1/16,
    "tps": 60,
    "name": "Runner",
    "blockSize": 32,
    "blockDensity": 0.05,
    "coinDensity": 0.005,
    "blockClumpRadius": 1,
    "blockClumpDensity": 0.8,
}

# Define path function that turns a relative path into an absolute path based on file location
def path(local: str) -> str:
    """Returns the absolute path of local path, based on this file location"""
    return os.path.join(os.path.dirname(__file__), local)

class Solid(pygame.sprite.Sprite):
    """Abstract solid entity that is guarenteed to have at least a hitbox.
    Includes collision detection logic
    """

    def __init__(self, hitbox: pygame.Rect):

        # Call super to interact with pygame sprite tools
        super().__init__()

        # Reference hitbox
        self.hitbox = hitbox

    def collided(self, other: Solid) -> bool:
        """Checks if the Solid's hitboxes collide"""
        return self.hitbox.colliderect(other.hitbox)

    def collisions(self, others: typing.Iterable[Solid]):
        """Returns a list of Solids in the list which are being collided with
        Uses self.collided as a collides function
        """
        return pygame.sprite.spritecollide(
            self, others, False, collided=lambda s, o: s.collided(o)
        )

class Block(Solid):
    """General block"""

    def __init__(self, position: typing.Tuple[int, int], image: pygame.Surface):

        # Reference image
        self.image = image

        # Create rect
        self.rect = self.image.get_rect()
        self.rect.x = position[0]
        self.rect.y = position[1]

        # Initiate as a solid, using image rect
        super().__init__(self.rect)

    def update(self):
        """Updates the block"""

class Inventory:
    """Class for managing an inventory
    Can be initalized referencing a Dict[str, int]
    """

    def __init__(self, dictionary: typing.Dict[str, int] = None):
        # Create dict if needed, otherwise reference
        # Order is a list of keys, saving the order of items
        # If the inventory is initialized with a dictionary,
        # the items currently in are ordered in whatever is returned by .keys()
        # when an item is added to the Inventory that doesnt already exist, it is appeneded to the order
        if dictionary:
            self.storage = dictionary
            self.order = list(dictionary.keys())
        else:
            self.storage = {}
            self.order = []

    def foo():
        pass
        #.a = 3

    def __getitem__(self, name: str) -> typing.Optional[int]:
        """Returns the quantity of the given item, 0 if it does not exist"""
        # Check if name exists
        if name in self.storage:
            return self.storage[name]
        return 0

    def __setitem__(self, name: str, quantity: int) -> None:
        """Sets the quantity of the given item"""
        self.storage[name] = quantity

    def __contains__(self, name: str) -> bool:
        """Checks if the given item is in the Inventory (0 counts)"""
        return name in self.storage

    def __len__(self):
        """Returns the number of items in the Inventory"""
        return len(self.storage)

    def __iter__(self):
        """Returns an iterator built out of the internal storage"""
        return iter(self.storage)

    def clean(self) -> typing.Set[str]:
        """Removes all items with 0 quantity, and returns a set of the names"""
        # Collect names with 0-val
        names = {name for name in self.storage if self.storage[name] == 0}
        # Pop given names
        for name in names:
            del self.storage[name]
        # Return deleted names
        return names

    def take(self, item: str, num: int) -> int:
        """Attempts to remove the specified amount of an item
        Raises ValueError if there is not enough
        Returns the amount remaining
        """
        # Check if there are enough in storage
        if self.storage[item] >= num:
            # Remove and return remaining
            self.storage[item] -= num
            return self.storage[item]
        # Raise ValueError if there is not enough
        raise ValueError("{self}.{item} is {self.storage[item]}, lower than specified {num}")

    def collect(self, other: Inventory) -> None:
        """Reads the current contents of the other inventory and adds them to this one
        Note: This takes a snapshot of the other inventory,
        it will not cause this one to be updated alongside the other
        """
        # Loop through elements of other
        for item in other:
            self[item] += other[item]

class Item(Solid):
    """Collectable item that has a loot Inventory"""

    def __init__(self, image: pygame.Surface, hitbox: pygame.Rect, loot: Inventory):

        # Call Solid init
        super().__init__(hitbox)

        # Reference image
        self.image = image

        # Create rect
        self.rect = self.image.get_rect()
        # Align rect with hitbox
        self.rect.center = self.hitbox.center

        # Reference inventory
        self.inventory = loot

class Grid:
    """Manages grid of tiles, mainly Blocks
    Data is a Dict with 2-d coordinate pairs as keys, entities as values
    Scale is the width and height in pixels of a tile
    """

    def __init__(self, scale: int):

        # Referenc scale
        self.scale = scale

        # Create data structure
        self.data = {}

    def __getitem__(self, key: typing.Tuple[int, int]):
        """Returns the object at key from the grid"""
        return self.data[key]

    def __setitem__(self, key: typing.Tuple[int, int], tile) -> None:
        """Adds an object to the data grid"""
        self.data[key] = tile

    def __delitem__(self, key: typing.Tuple[int, int]):
        """Deletes an object from the data grid"""
        del self.data[key]

    def __contains__(self, key: typing.Tuple[int, int]):
        """Checks if the key is in the data grid"""
        return key in self.data

    def rect(self, pos: typing.Tuple[int, int]) -> pygame.Rect:
        """Returns a rect bounding the given tile coordinate
        Considers (0, 0) tile to have an origin at (0, 0), extending down-left
        """
        return pygame.Rect(pos[0]*self.scale, pos[1]*self.scale, self.scale, self.scale)

    def index(self, pos: pygame.Vector2) -> typing.Tuple[int, int]:
        """Returns a tile index using the given position vector / rect (uses topleft origin)
        Considers top and left edges to be part of a tile
        """
        return (pos[0]//self.scale, pos[1]//self.scale)

    def viewbox_tiles(self, viewbox: Viewbox):
        """Returns a set of tile coordinates viewable by the given viewbox"""

        # Find top-left and bottom-right bounds
        topLeft = self.index(viewbox.rect.topleft)
        bottomRight = self.index(viewbox.rect.bottomright)

        # Return generated set
        return {
            (column, row)
            for column in range(topLeft[0], bottomRight[0]+1)
            for row in range(topLeft[1], bottomRight[1]+1)
        }

    def add_block(self, index: typing.Tuple[int, int], image: pygame.Surface) -> Block:
        """Creates a Block at the given index, with appropiate rect, and returns it
        The image should probably be a multiple of .scale"""
        block = Block(self.rect(index).topleft, image)
        self[index] = block
        return block

    def generate_block(self, index: typing.Tuple[int, int], image: pygame.Surface) -> Block:
        """Generates a Block at the given index, with appropiate rect, and returns it
        Does not add the block to the grid, it only generates one that would fit
        The image should probably be a multiple of .scale"""
        return Block(self.rect(index).topleft, image)

class Keyset:
    """Gives symbolic names to pygame keys
    Allows linking multiple keys to a single name,
    so a check for the name will succeed if any of the keys are pressed
    """

    def __init__(self, **kwargs: typing.Dict[str, typing.Union[int, typing.Set[int]]]):
        # Reference links
        self.names = kwargs

        # Change any single values to singleton sets
        for name, keys in self.names.items():
            try:
                iter(keys)
            except TypeError:
                # Non iterable, wrap in singleton set
                self.names[name] = {keys}

    def held(self, name: str, keyboard: dict) -> bool:
        """Checks if any of the keys linked to a name are held down in a pygame keyboard dict"""
        return any(keyboard[key] for key in self.names[name])

    def has(self, name: str, key: int) -> bool:
        "Checks if the given key value is any of the keys for the given name"
        return key in self.names[name]


class Player(Solid):
    """Main controllable character of the game
    Player(image: Surface, hitbox: Rect, keyConfig: dict, physicsConfig: dict)
    keyset is a Keyset
    Currently requires "jump", "left", "right" keyConfigs
    Use Player.keyDictionary to automatically generate a compatible dictionary
    physicsConfig is similar to keyConfig, but provides physics constants
    Use Player.physicsDictionary to automatically generate a compatible dictionary
    """

    @classmethod
    def keyDictionary(cls, jump: int, left: int, right: int) -> typing.Dict[str, int]:
        """Automatically produces a keyConfig in the format expected by the constructor"""
        return {"jump": jump, "left": left, "right": right}

    @classmethod
    def physicsDictionary(cls, jump: int, gravity: int, maxFall: int,
                          maxSpeed: int, speed: int, jumps: int) -> typing.Dict[str, int]:
        """Automatically produces a physicsConfig in the format expected by the constructor
        Data usages:
        jump - jump power set to yspeed on jump
        gravity - decrease in yspeed every tick
        maxFall - maximum speed achievable by gravity
        maxSpeed - maximum running speed
        speed - horizontal acceleration and decelleration
        jumps - available jumps refreshed by ground contact"""
        return {
            "jump": jump, "gravity": gravity, "maxFall": maxFall,
            "maxSpeed": maxSpeed, "speed": speed, "jumps": jumps
        }

    def __init__(self, image: pygame.Surface,
                 hitbox: pygame.Rect,
                 keyset: Keyset,
                 physicsConfig: typing.Dict[str, int]
                ):

        # Call Solid init
        super().__init__(hitbox)

        # Reference image
        self.image = image

        # Generate rect from hitbox, starting centered on the hitbox
        self.rect = self.image.get_rect()
        self.rect.center = self.hitbox.center

        # Reference keyConfig
        self.keyset = keyset

        # Reference physics config
        self.physicsConfig = physicsConfig

        # Create movement vector
        self.speed = pygame.Vector2(0, 0)

        # Create jumps
        self.jumps = 0

        # Create inventory
        self.inventory = Inventory()

    def move(self, displacement: pygame.Vector2, solids: pygame.sprite.Group):
        """Moves the Player by the given displacement, stopping on collision
        Will reset respective velocities on collision
        """

        # Attempt horizontal movement
        self.hitbox.x += displacement.x
        # Check for collisions
        # Get collisions
        collisions = self.collisions(solids)
        # Resolve collisions if existant
        if collisions:
            # Find closest collision
            # Differentiate based on direction
            if displacement.x > 0: # Moving right, collides with left edges
                # Grabs the collision with the lowest left edge
                collision = min(collisions, key=lambda c: c.hitbox.left)
                # Snap to edge
                self.hitbox.right = collision.hitbox.left
            else: # Moving left, or hypothetically a collision situation without movement
                # Grabs the collision with the highest right edge
                collision = max(collisions, key=lambda c: c.hitbox.right)
                # Snap to edge
                self.hitbox.left = collision.hitbox.right
            # Stop movement
            self.speed.x = 0

        # Note: We evaluate y-displacement dependently after x-displacement for multiple reasons
        # 1) Im lazy, dont want to handle literal corner case
        # 2) Allow slipping around corners while jumping/falling, should feel smoother

        # Attempt vertical movement
        self.hitbox.y += displacement.y
        # Check for collisions
        # Get collisions
        collisions = self.collisions(solids)
        # Resolve collisions if existant
        if collisions:
            # Find closest collision
            # Differentiate based on direction
            if displacement.y > 0: # Moving down, collides with top edges
                # Grabs the collision with the lowest top edge
                collision = min(collisions, key=lambda c: c.hitbox.top)
                # Snap to edge
                self.hitbox.bottom = collision.hitbox.top
                # Reset jumps
                self.jumps = self.physicsConfig["jumps"]
            else: # Moving up, or hypothetically a collision situation without movement
                # Grabs the collision with the highest bottom edge
                collision = max(collisions, key=lambda c: c.hitbox.bottom)
                # Snap to edge
                self.hitbox.top = collision.hitbox.bottom
            # Stop movement
            self.speed.y = 0

    def collect(self, collectables: typing.Iterable[Item]):
        """Collects and kills any colliding Items"""
        # Iterates through what will probably be a list/sprite group
        # Only iterates through the ones in collision
        for item in self.collisions(collectables):
            # Collect the inventory of the item
            self.inventory.collect(item.inventory)
            # Remove the collectable
            item.kill()

    def accelerate_x(self, change: int):
        """Updates the horizontal speed, respecting config maxSpeed"""
        # Only attempt if under max
        if abs(self.speed.x) < self.physicsConfig["maxSpeed"]:
            self.speed.x += change
            # Cap speed
            # Lower limit
            if self.speed.x < -self.physicsConfig["maxSpeed"]:
                self.speed.x = -self.physicsConfig["maxSpeed"]
            # Upper limit
            elif self.speed.x > self.physicsConfig["maxSpeed"]:
                self.speed.x = self.physicsConfig["maxSpeed"]

    def decelerate_x(self, change: int):
        """Updates the horizontal speed, grounding at 0
        Works expecting 'change' to be positive, and changes speed towards 0
        """
        # Started positive
        if self.speed.x > 0:
            self.speed.x -= change
            # Clip at 0
            if self.speed.x < 0:
                self.speed.x = 0
        # Started negative
        elif self.speed.x < 0:
            self.speed.x += change
            # Clip at 0
            if self.speed.x > 0:
                self.speed.x = 0

    def impulse(self, inputs: dict):
        """Updates speed vector based on an inputs dict
        The inputs should be sourced from a Game.inputs
        """

        # Calculate horizontal direction based on keypresses
        # Casts True/False -> 1/0 for whether keys are pressed,
        # -1: left, 0: none, 1: right
        direction = (
            int(self.keyset.held("right", inputs["keyboard"]))
            - int(self.keyset.held("left", inputs["keyboard"]))
        )

        # Move based on direction
        # Left movement
        if direction == -1:
            # Accelerate attempt
            self.accelerate_x(-self.physicsConfig["speed"])
        # Right movement
        elif direction == 1:
            # Attempt to accelerate
            self.accelerate_x(self.physicsConfig["speed"])
        # No key pressed or cancel
        else:
            # Decelerate
            self.decelerate_x(self.physicsConfig["speed"])

        # Check events for keypresses
        for event in inputs["events"]:
            # Select keydown events
            if event.type == pygame.KEYDOWN:
                # Check for jump key
                if self.keyset.has("jump", event.key) and self.jumps > 0:
                    self.speed.y = -self.physicsConfig["jump"]
                    # Decrease jumps remaining
                    self.jumps -= 1

        # Apply gravity if  below max
        if self.speed.y < self.physicsConfig["maxFall"]:
            self.speed.y += self.physicsConfig["gravity"]

    def update(self, game: Game):
        """Updates the player relative to the given Game"""

        # Calculate impulse
        # Updates self.speed
        self.impulse(game.inputs)

        # Move using object method
        self.move(self.speed, game.solids)

        # Collect any collectables
        self.collect(game.collectables)

        # Align visual rect with actual hitbox
        self.rect.center = self.hitbox.center

# A Viewbox represents a view, and provides easy ways to produce a surface
# that only includes sprites in a specific region, with a offset
class Viewbox:
    """Represents the view of the game, mainly for displacement"""

    def __init__(self, rect: pygame.Rect):

        # Reference rect
        self.rect = rect

        # Create surface
        self.image = pygame.Surface(self.rect.size)

    def render(self, sprites: pygame.sprite.Group) -> None:
        """Draws the given sprites (as a Group) onto the surface
        Adjusts position based on viewbox offset
        """
        # Access each sprite individually for offsetting
        for sprite in sprites:
            # Moves the sprites the opposite direction of viewbox location,
            # so as the viewbox "moves", the sprites are moved onto it
            # e.g. viewbox offset: (5, 5) will make a sprite at (5, 5) be drawn at (0, 0)
            self.image.blit(sprite.image, sprite.rect.move(-self.rect.x, -self.rect.y))

# Game object, used so that we can pass a single object into things like a Player
# which can then read what it needs. Should be more scalable than dicts
class Game:
    """Stores information about game state and provides methods for updating/modifying the state
    images: dictionary of surfaces used for various entities
    scale: the scale of tiles in the game, especially used by the grid"""

    def __init__(self, images: typing.Dict[str, pygame.Surface], player: Player, scale: int):

        # Reference image set
        self.images = images

        # Reference player
        self.player = player

        # Create sprite groups
        # Physical blocks for collisions
        self.solids = pygame.sprite.Group()
        # Inventories that are collected on contact
        self.collectables = pygame.sprite.Group()

        # Empty spaces used for the minimap and grid
        self.spaces = pygame.sprite.Group()

        # Create grid object, which stores blocks in a ordered manner, mostly for generation
        self.grid = Grid(scale)

        # Initialize input dictionary
        self.inputs = {"events": None, "keyboard": None}

    def generate(self, tiles: typing.Collection[tuple], densityConfig: dict, destructive=False):
        """Generates tiles into the Game's grid, generates on the tiles given
        Uses densityConfig for generation probabilities
        If destructive is true, then tiles will be generated over old ones,
        if false, if a tile that is to be generated already exists it is left alone.
        Note that the generation can splash out of the tiles given in clump generation
        """
        # Generate tiles in uncharted tiles
        for tile in tiles:
            if destructive or tile not in self.grid:
                # Generate float [0, 1)
                val = random.random()
                # Generate tile based on val
                # Coin density takes precedence over blocks
                if val < densityConfig["coinDensity"]:
                    self.collectables.add(Item(
                        self.images["coin"], self.grid.rect(tile), Inventory({"coin": 1})
                    ))
                    self.spaces.add(self.grid.add_block(tile, self.images["space"]))
                elif val < densityConfig["blockDensity"]:
                    # Attempt "splash" generation
                    # Create main block
                    self.solids.add(self.grid.add_block(tile, self.images["block"]))
                    # Create range object
                    area = range(
                        -densityConfig["blockClumpRadius"],
                        densityConfig["blockClumpRadius"]+1
                    )
                    # Iterate through both axes
                    for x in area:
                        for y in area:
                            # Get val for generation possibility
                            if random.random() < densityConfig["blockClumpDensity"]:
                                if destructive or (tile[0]+x, tile[1]+y) not in self.grid:
                                    # Generate offset based on current x,y
                                    self.solids.add(self.grid.add_block(
                                        (tile[0]+x, tile[1]+y), self.images["block"]
                                    ))
                else:
                    # Signifies that this has been generated, just without block/coin
                    self.spaces.add(self.grid.add_block(tile, self.images["space"]))

    def update(self, events, viewbox: Viewbox):
        """Updates the Game, interacting entities appropriately
        Reads read-inputs (i.e. the keyboard) itself,
        but requires pygame events passed in to be non-destructive
        Uses a passed viewbox to know what needs to be generated
        """
        # Update inputs
        self.inputs["events"] = events
        self.inputs["keyboard"] = pygame.key.get_pressed()

        # Update player with this game
        self.player.update(self)

        # Generate uncharted territory
        # Pull visible tiles
        visibleTiles = self.grid.viewbox_tiles(viewbox)

        # Generate tiles, using global config for now
        self.generate(visibleTiles, config)

def load_images() -> typing.Dict[str, pygame.Surface]:
    """Loads the projects image resources

    Returns a dictionary of <name>: surface,
    where <name> is the name of the file with the extension stripped
    """
    # Construct a dictionary to be returned
    return {
        # Creates a key by taking everything up to the first '.' in file name
        # Value is pygame surface loaded from file name, converted
        name.split(".")[0]: pygame.image.load(path(os.path.join("images", name))).convert_alpha()
        # Checks every name in 'images' subdirectory | pylint: disable=bad-continuation
        for name in os.listdir(path("images"))
        # Safety check to prevent trying to load directories
        if os.path.isfile(path(os.path.join("images", name)))
    }

def main():
    """Main game script"""

    # Init pygame
    pygame.init()

    # Create clock
    clock = pygame.time.Clock()

    # Create viewbox
    viewbox = Viewbox(pygame.Rect(0, 0, config["windowWidth"], config["windowHeight"]))
    # Create minimap
    minimap = Viewbox(pygame.Rect(0, 0, config["minimapWidth"], config["minimapHeight"]))

    # Setup window
    screen = pygame.display.set_mode(viewbox.rect.size)
    pygame.display.set_caption(config["name"])
    tps = config["tps"]

    # Load images
    images = load_images()

    # Create player
    player = Player(
        images["player"], pygame.Rect(0, 0, 20, 20),
        Keyset(
            jump={pygame.K_UP, pygame.K_w},
            left={pygame.K_LEFT, pygame.K_a},
            right={pygame.K_RIGHT, pygame.K_d},
        ),
        Player.physicsDictionary(
            jump=19, gravity=1, maxFall=32,
            maxSpeed=7, speed=2, jumps=1,
        ),
    )

    # Create game state
    game = Game(images, player, config["blockSize"])

    # Create block below player
    game.solids.add(game.grid.add_block((0, 3), images["block"]))

    # Main loop
    running = True
    tick = 0
    while running:

        # Dump event queue into reference
        events = pygame.event.get()

        # Check for interesting events
        for event in events:

            # QUIT event comes from closing the window, etc
            if event.type == pygame.QUIT:
                running = False

        # Skips the rest of the loop if the program is quitting
        if running:

            # Update the game
            game.update(events, viewbox)

            # Refresh the viewbox
            # Lock viewbox to follow player
            viewbox.rect.center = game.player.rect.center
            # Fill over old image
            viewbox.image.fill((15, 15, 15))
            # Render the blocks and then player into the viewbox
            viewbox.render(itertools.chain(game.solids, game.collectables, (player, )))

            # Refresh the minimap
            # Lock viewbox to follow player
            minimap.rect.center = player.rect.center
            # Fill over old image
            minimap.image.fill((31, 31, 31))
            # Render the blocks and then player into the viewbox
            minimap.render(itertools.chain(game.solids, game.spaces, (player, )))

            # Display the viewbox onto the screen
            screen.blit(viewbox.image, (0, 0))
            # Display the scaled minimap
            screen.blit(
                pygame.transform.scale(
                    minimap.image, (
                        int(config["minimapWidth"]*config["minimapScale"]),
                        int(config["minimapHeight"]*config["minimapScale"])
                    )
                ), (0, 0)
            )

            # Flip display
            pygame.display.flip()

            # Increment tick
            tick = (tick + 1)# % cycle_length
            # Limit to determined tps
            clock.tick(tps)

# TODO inventory displays / popups. other UI elements like labels, buttons? <- Big rabbit hole
# main script pattern
if __name__ == "__main__":
    main()
