"""Sidescrolling runner game"""

# Import future annotations
from __future__ import annotations

# Import core modules
import os
import typing
import random

# Import pygame
import pygame

# Define config
config = {
    "windowWidth": 512,
    "windowHeight": 512,
    "tps": 60,
    "name": "Runner",
    "blockSize": 32,
    "blockDensity": 0.2,
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
    def physicsDictionary(cls, jump: int, gravity: int, move: int) -> typing.Dict[str, int]:
        """Automatically produces a keyConfig in the format expected by the constructor"""
        return {"jump": jump, "gravity": gravity, "move": move}

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
            else: # Moving up, or hypothetically a collision situation without movement
                # Grabs the collision with the highest bottom edge
                collision = max(collisions, key=lambda c: c.hitbox.bottom)
                # Snap to edge
                self.hitbox.top = collision.hitbox.bottom
            # Stop movement
            self.speed.y = 0

    def update(self, inputs: typing.Dict):
        """Updates the player using the given input"""

        # Parse the input
        # Check for left/right movement presses
        # Reset to 0 before more sophisticated accel x system
        # TODO
        self.speed.x = 0
        if inputs["keyboard"][self.keyConfig["left"]]:
            self.speed.x -= self.physicsConfig["move"]
        if inputs["keyboard"][self.keyConfig["right"]]:
            self.speed.x += self.physicsConfig["move"]

        # Check events for keypresses
        for event in inputs["events"]:
            # Select keydown events
            if event.type == pygame.KEYDOWN:
                # Check for jump key
                if event.key == self.keyConfig["jump"]:
                    self.speed.y = -self.physicsConfig["jump"]

        # Apply gravity
        self.speed.y += self.physicsConfig["gravity"]

        # Move using object method
        self.move(self.speed, inputs["solids"])

        # Align visual rect with actual hitbox
        self.rect.center = self.hitbox.center



def inputsDictionary(events, keyboard, solids: pygame.sprite.Group = None) -> typing.Dict:
    """Returns a inputs dictionary in the format expected by Entities
    solids should be provided to entities performing collisions
    """
    return {"events": events, "keyboard": keyboard, "solids": solids}

# Define viewbox
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


def main():
    """Main game script"""

    # Init pygame
    pygame.init()

    # Create viewbox
    viewbox = Viewbox(pygame.Rect(0, 0, config["windowWidth"], config["windowHeight"]))

    # Create clock
    clock = pygame.time.Clock()

    # Setup window
    screen = pygame.display.set_mode(viewbox.rect.size)
    pygame.display.set_caption(config["name"])
    tps = config["tps"]

    # Load images
    images = ("block", "player")
    # Convert loaded surfaces to screen format
    images = {name: pygame.image.load(path(name+".png")).convert() for name in images}

    # Create player
    player = Player(
        images["player"], images["player"].get_rect(),
        Player.keyDictionary(pygame.K_UP, pygame.K_LEFT, pygame.K_RIGHT),
        Player.physicsDictionary(15, 1, 7),
    )

    # Initiate block group
    blocks = pygame.sprite.Group()

    # Create block grid to track blocks and explored area
    grid = Grid(config["blockSize"])

    # Create block below player
    blocks.add(grid.add_block((0, 3), images["block"]))

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

        # Check other sources of input, e.g. the keyboard
        keyboard = pygame.key.get_pressed()

        # Skips the rest of the loop if the program is quitting
        if running:

            # Generate blocks in uncharted territory
            # Pull visible tiles
            visibleTiles = grid.viewbox_tiles(viewbox)
            # Generate tiles in uncharted tiles
            for tile in visibleTiles:
                if tile not in grid:
                    if random.random() < config["blockDensity"]:
                        blocks.add(grid.add_block(tile, images["block"]))
                    else:
                        grid[tile] = None

            # Create input dict
            inputs = inputsDictionary(events, keyboard, blocks)

            # Update blocks
            blocks.update()

            # Update player
            player.update(inputs)

            # Lock viewbox to follow player
            viewbox.rect.center = player.rect.center

            # Refresh the viewbox
            # Fill over old image
            viewbox.image.fill((31, 31, 31))
            # Render the blocks into the viewbox
            viewbox.render(blocks)
            # Render player # TODO make visibles sprite group
            viewbox.render((player, ))

            # Slap the viewbox onto the screen
            screen.blit(viewbox.image, (0, 0))

            # Flip display
            pygame.display.flip()

            # Increment tick
            tick = (tick + 1)# % cycle_length
            # Limit to determined tps
            clock.tick(tps)

# main script pattern
if __name__ == "__main__":
    main()
