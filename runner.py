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
        if dictionary:
            self.storage = dictionary
        else:
            self.storage = {}

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

class Player(Solid):
    """Main controllable character of the game
    Player(image: Surface, hitbox: Rect, keyConfig: dict)
    keyConfig is a {str: int} dictionary that maps names to keycodes
    Currently requires "jump", "left", "right" keyConfigs
    Use Player.keyDictionary to automatically generate a compatible dictionary
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
                 hitbox: pygame.Rect, keyConfig: typing.Dict[str, int],
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
        self.keyConfig = keyConfig

        # Reference physics config
        self.physicsConfig = physicsConfig

        # Create movement vector
        self.speed = pygame.Vector2(0, 0)

        # Create jumps
        self.jumps = 0

    def move(self, displacement: pygame.Vector2, solids: pygame.sprite.Group):
        """Moves the Player by the given displacement, stopping on collision
        Will reset respective velocities on collision
        """

        # Attempt horizontal movement
        self.hitbox.x += displacement.x
        # Check for collisions
        # Get collisions
        collisions = pygame.sprite.spritecollide(
            self, solids, False, collided=lambda s, o: s.collided(o)
        )
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
        collisions = pygame.sprite.spritecollide(
            self, solids, False, collided=lambda s, o: s.collided(o)
        )
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

    def update(self, game: Game):
        """Updates the player relative to the given Game"""

        # Parse the input
        # Check for left/right movement presses
        impulse = 0
        if game.inputs["keyboard"][self.keyConfig["left"]]:
            impulse -= 1
        # Allow cancelling
        if game.inputs["keyboard"][self.keyConfig["right"]]:
            impulse += 1

        # Move based on impulse
        # Left movement
        if impulse == -1:
            # Allow acceleration under cap
            if abs(self.speed.x) < self.physicsConfig["maxSpeed"]:
                self.speed.x -= self.physicsConfig["speed"]
                # Cap speed
                if self.speed.x < -self.physicsConfig["maxSpeed"]:
                    self.speed.x = -self.physicsConfig["maxSpeed"]
        # Right movement
        elif impulse == 1:
            # Allow acceleration under cap
            if abs(self.speed.x) < self.physicsConfig["maxSpeed"]:
                self.speed.x += self.physicsConfig["speed"]
                # Cap speed
                if self.speed.x > self.physicsConfig["maxSpeed"]:
                    self.speed.x = self.physicsConfig["maxSpeed"]
        # This clause triggers if neither or both key is pressed
        else:
            # Decrease speed
            if self.speed.x > 0:
                self.speed.x -= self.physicsConfig["speed"]
                # Clip at 0
                if self.speed.x < 0:
                    self.speed.x = 0
            elif self.speed.x < 0:
                self.speed.x += self.physicsConfig["speed"]
                # Clip at 0
                if self.speed.x > 0:
                    self.speed.x = 0

        # Check events for keypresses
        for event in game.inputs["events"]:
            # Select keydown events
            if event.type == pygame.KEYDOWN:
                # Check for jump key
                if event.key == self.keyConfig["jump"] and self.jumps > 0:
                    self.speed.y = -self.physicsConfig["jump"]
                    # Decrease jumps remaining
                    self.jumps -= 1

        # Apply gravity if  below max
        if self.speed.y < self.physicsConfig["maxFall"]:
            self.speed.y += self.physicsConfig["gravity"]

        # Move using object method
        self.move(self.speed, game.solids)

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

        # Generate tiles in uncharted tiles
        for tile in visibleTiles:
            if tile not in self.grid:
                # Generate float [0, 1)
                val = random.random()
                # Generate tile based on val
                if val < config["coinDensity"]:
                    self.collectables.add(self.grid.generate_block(tile, self.images["coin"]))
                    self.spaces.add(self.grid.add_block(tile, self.images["space"]))
                elif val < config["blockDensity"]:
                    self.solids.add(self.grid.add_block(tile, self.images["block"]))
                else:
                    self.spaces.add(self.grid.add_block(tile, self.images["space"]))

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

    # Load images from files
    # This has to be down after starting the window so we can .convert
    images = ("block", "player", "coin")
    # Convert loaded surfaces to screen format
    images = {name: pygame.image.load(path(name+".png")).convert_alpha() for name in images}
    # Manufacture filler image
    images["space"] = pygame.Surface((config["blockSize"], config["blockSize"])).convert()
    images["space"].fill((63, 63, 63))

    # Create player
    player = Player(
        images["player"], pygame.Rect(0, 0, 20, 20),
        Player.keyDictionary(pygame.K_UP, pygame.K_LEFT, pygame.K_RIGHT),
        Player.physicsDictionary(19, 1, 32, 9, 2, 1),
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

# main script pattern
if __name__ == "__main__":
    main()
