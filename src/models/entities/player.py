"""Player character model."""
from __future__ import annotations

from enum import Enum, auto
from typing import Dict, Optional
from pathlib import Path
import random
import pygame as pg

from src.models.entities.character import Character
from src.models.animation import Animation, AnimationSet
from src.core.constants import (
    PlayerConstants, GRAVITY, JUMP_SPEED, MAX_FALL_SPEED,
    BASE_MOVEMENT_SPEED, SPRINT_MULTIPLIER, DOUBLE_CLICK_THRESHOLD_MS,
    AssetPaths
)


class PlayerState(Enum):
    """Player animation states."""
    
    IDLE = auto()
    WALK = auto()
    RUN = auto()
    ATTACK_LIGHT_1 = auto()
    ATTACK_LIGHT_2 = auto()
    ATTACK_HEAVY = auto()
    BLOCK = auto()
    HURT = auto()
    DEATH = auto()


class PlayerAction(Enum):
    """Player input actions."""
    
    MOVE_LEFT = auto()
    MOVE_RIGHT = auto()
    JUMP = auto()
    SPRINT = auto()
    BLOCK = auto()
    ATTACK_LIGHT = auto()
    ATTACK_HEAVY = auto()


class Player(Character):
    """Player character with full movement and combat capabilities."""
    
    def __init__(self, x: float, y: float, health: int = PlayerConstants.MAX_HEALTH) -> None:
        """Initialize player at given position."""
        super().__init__(x, y, health, PlayerConstants.SPRITE_SIZE)
        
        # Player stats
        self._mana = PlayerConstants.MAX_MANA
        self._max_mana = PlayerConstants.MAX_MANA
        self._coins = 0
        
        # Movement state
        self._move_direction = 0  # -1 left, 0 none, 1 right
        self._is_sprinting = False
        self._jump_requested = False
        
        # Combat state
        self._is_blocking = False
        self._last_right_click_time = 0
        
        # Animation state
        self._current_state = PlayerState.IDLE
        self._animations = self._load_animations()
        self._animations.set_state(self._current_state)
        
        # Initialize image
        self.image = self._animations.get_current_frame()
        
        # Set physics constraints
        self.max_velocity = pg.math.Vector2(
            BASE_MOVEMENT_SPEED * SPRINT_MULTIPLIER * 60,  # Max horizontal speed
            MAX_FALL_SPEED * 60  # Max fall speed
        )
    
    # Properties
    @property
    def mana(self) -> int:
        """Get current mana."""
        return self._mana
    
    @property
    def max_mana(self) -> int:
        """Get maximum mana."""
        return self._max_mana
    
    @property
    def mana_percentage(self) -> float:
        """Get mana as percentage (0.0 to 1.0)."""
        return self._mana / self._max_mana if self._max_mana > 0 else 0.0
    
    @property
    def coins(self) -> int:
        """Get current coins."""
        return self._coins
    
    @property
    def is_blocking(self) -> bool:
        """Check if player is blocking."""
        return self._is_blocking
    
    @property
    def current_state(self) -> PlayerState:
        """Get current animation state."""
        return self._current_state
    
    # Input handling
    def handle_action(self, action: PlayerAction, pressed: bool) -> None:
        """Handle player input action."""
        if action == PlayerAction.MOVE_LEFT:
            self._move_direction = -1 if pressed else (self._move_direction if self._move_direction != -1 else 0)
        elif action == PlayerAction.MOVE_RIGHT:
            self._move_direction = 1 if pressed else (self._move_direction if self._move_direction != 1 else 0)
        elif action == PlayerAction.JUMP and pressed and not self._is_blocking and self.on_ground:
            # Register jump only if not blocking and player is on ground
            self._jump_requested = True
        elif action == PlayerAction.SPRINT:
            self._is_sprinting = pressed
        elif action == PlayerAction.BLOCK:
            self._is_blocking = pressed
            # Cancel any pending jump when entering block state
            if pressed:
                self._jump_requested = False
                self._enter_state(PlayerState.BLOCK)
            elif self._current_state == PlayerState.BLOCK:
                self._enter_state(PlayerState.IDLE)
        elif action == PlayerAction.ATTACK_LIGHT:
            self._is_blocking = pressed
        elif action == PlayerAction.ATTACK_HEAVY:
            self._is_blocking = pressed
    
    def handle_mouse_click(self, button: int, current_time: int) -> None:
        """Handle mouse click for attacks."""
        if not self._can_attack():
            return
        
        if button == 1:  # Left click - light attack
            state = random.choice([PlayerState.ATTACK_LIGHT_1, PlayerState.ATTACK_LIGHT_2])
            self._enter_state(state)
        elif button == 3:  # Right click - check for double click
            if current_time - self._last_right_click_time <= DOUBLE_CLICK_THRESHOLD_MS:
                self._enter_state(PlayerState.ATTACK_HEAVY)
                self._last_right_click_time = 0
            else:
                self._last_right_click_time = current_time
    
    # Resource management
    def add_coins(self, amount: int) -> None:
        """Add coins to player inventory."""
        self._coins = max(0, self._coins + amount)
    
    def spend_coins(self, amount: int) -> bool:
        """Attempt to spend coins. Returns True if successful."""
        if self._coins >= amount:
            self._coins -= amount
            return True
        return False
    
    def add_mana(self, amount: int) -> None:
        """Restore mana to player."""
        self._mana = min(self._max_mana, self._mana + amount)
    
    def use_mana(self, amount: int) -> bool:
        """Attempt to use mana. Returns True if successful."""
        if self._mana >= amount:
            self._mana -= amount
            return True
        return False
    
    # Overridden methods
    def take_damage(self, amount: int) -> bool:
        """Apply damage with blocking reduction."""
        if self._is_blocking:
            amount = max(1, int(amount * PlayerConstants.BLOCK_DAMAGE_REDUCTION))
        
        if super().take_damage(amount):
            if self.is_alive:
                self._enter_state(PlayerState.HURT)
            return True
        return False
    
    def _on_death(self) -> None:
        """Handle player death."""
        self._enter_state(PlayerState.DEATH)
    
    def update(self, delta_time: float) -> None:
        """Update player state - override to NOT call update_physics."""
        # Update invulnerability timer
        if self._invulnerable and self._invulnerable_timer > 0:
            self._invulnerable_timer -= delta_time
            if self._invulnerable_timer <= 0:
                self._invulnerable = False
                self._invulnerable_timer = 0
        
        # DON'T call update_physics here - physics are handled in game scene
        # self.update_physics(delta_time)  # REMOVED
        
        # Character-specific updates
        self._update_character(delta_time)
    
    def _update_character(self, delta_time: float) -> None:
        """Update player-specific logic."""
        # Handle jump
        if self._jump_requested and self.on_ground and not self._is_blocking:
            self.velocity.y = JUMP_SPEED * 60  # Convert to pixels per second
            self.on_ground = False
            self._jump_requested = False
        
        # Apply gravity
        if not self.on_ground:
            self.acceleration.y = GRAVITY * 60 * 60  # Convert to pixels per second squared
        else:
            self.acceleration.y = 0
            self.velocity.y = 0
        
        # Handle horizontal movement
        speed = BASE_MOVEMENT_SPEED * (SPRINT_MULTIPLIER if self._is_sprinting else 1.0)
        self.velocity.x = self._move_direction * speed * 60  # Convert to pixels per second
        
        # Reset horizontal acceleration to prevent accumulation
        self.acceleration.x = 0
        
        # Update facing direction
        if self._move_direction < 0:
            self.facing_left = True
        elif self._move_direction > 0:
            self.facing_left = False
        
        # Update animation state machine
        self._update_state_machine()
        
        # Update animation
        self._animations.update(delta_time)
        self.image = self._animations.get_current_frame(flip_x=self.facing_left)
    
    # Private methods
    def _can_attack(self) -> bool:
        """Check if player can initiate an attack."""
        return self._current_state in {PlayerState.IDLE, PlayerState.WALK, PlayerState.RUN}
    
    def _enter_state(self, new_state: PlayerState) -> None:
        """Transition to a new animation state."""
        if self._current_state == new_state:
            return
        
        self._current_state = new_state
        self._animations.set_state(new_state)
    
    def _update_state_machine(self) -> None:
        """Update animation state based on player status."""
        # Handle non-interruptible states
        if self._current_state in {PlayerState.ATTACK_LIGHT_1, PlayerState.ATTACK_LIGHT_2, 
                                   PlayerState.ATTACK_HEAVY, PlayerState.HURT}:
            if self._animations.is_finished():
                self._enter_state(PlayerState.IDLE)
            return
        
        if self._current_state == PlayerState.DEATH:
            if self._animations.is_finished():
                self.kill()
            return
        
        if self._current_state == PlayerState.BLOCK:
            return
        
        # Determine movement state
        if self._move_direction != 0:
            desired_state = PlayerState.RUN if self._is_sprinting else PlayerState.WALK
        else:
            desired_state = PlayerState.IDLE
        
        self._enter_state(desired_state)
    
    def _load_animations(self) -> AnimationSet:
        """Load all player animations."""
        base_path = Path(AssetPaths.HERO_KNIGHT)
        animation_configs = {
            PlayerState.IDLE: ("idle", PlayerConstants.ANIMATION_FPS["idle"], True),
            PlayerState.WALK: ("walk", PlayerConstants.ANIMATION_FPS["walk"], True),
            PlayerState.RUN: ("run", PlayerConstants.ANIMATION_FPS["run"], True),
            PlayerState.ATTACK_LIGHT_1: ("attack_1", PlayerConstants.ANIMATION_FPS["attack_1"], False),
            PlayerState.ATTACK_LIGHT_2: ("attack_2", PlayerConstants.ANIMATION_FPS["attack_2"], False),
            PlayerState.ATTACK_HEAVY: ("heavy_attack", PlayerConstants.ANIMATION_FPS["heavy_attack"], False),
            PlayerState.BLOCK: ("defend", PlayerConstants.ANIMATION_FPS["defend"], True),
            PlayerState.HURT: ("hurt", PlayerConstants.ANIMATION_FPS["hurt"], False),
            PlayerState.DEATH: ("death", PlayerConstants.ANIMATION_FPS["death"], False),
        }
        
        animations = {}
        for state, (folder, fps, loop) in animation_configs.items():
            frames = self._load_animation_frames(base_path / folder)
            animations[state] = Animation(frames, fps, loop=loop)
        
        return AnimationSet(animations)
    
    def _load_animation_frames(self, folder_path: Path) -> list[pg.Surface]:
        """Load and scale animation frames from folder."""
        frames = []
        
        if not folder_path.exists():
            # Return single placeholder frame
            placeholder = pg.Surface(PlayerConstants.SPRITE_SIZE, pg.SRCALPHA)
            placeholder.fill((255, 0, 255))
            return [placeholder]
        
        # Load all PNG files in order
        for image_path in sorted(folder_path.glob("*.png")):
            try:
                frame = pg.image.load(str(image_path)).convert_alpha()
                scaled_frame = pg.transform.scale(frame, PlayerConstants.SPRITE_SIZE)
                frames.append(scaled_frame)
            except pg.error:
                continue
        
        # Ensure at least one frame
        if not frames:
            placeholder = pg.Surface(PlayerConstants.SPRITE_SIZE, pg.SRCALPHA)
            placeholder.fill((255, 0, 255))
            frames.append(placeholder)
        
        return frames