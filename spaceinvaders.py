#!/usr/bin/env python

# Space Invaders
# Created by Lee Robinson

import sys
from itertools import cycle
from os.path import abspath, dirname
from random import choice

from pygame import display, event, font, image, init, key, \
    mixer, time, transform, Surface
from pygame.constants import QUIT, KEYDOWN, KEYUP, USEREVENT, \
    K_ESCAPE, K_LEFT, K_RIGHT, K_SPACE
from pygame.event import Event
from pygame.mixer import Sound
from pygame.sprite import groupcollide, Group, DirtySprite, LayeredDirty

DEBUG = True

BASE_PATH = abspath(dirname(__file__))
FONT_PATH = BASE_PATH + '/fonts/'
IMAGE_PATH = BASE_PATH + '/images/'
SOUND_PATH = BASE_PATH + '/sounds/'

# Colors (R, G, B)
WHITE = (255, 255, 255)
GREEN = (78, 255, 87)
YELLOW = (241, 255, 0)
BLUE = (80, 255, 239)
PURPLE = (203, 0, 255)
RED = (237, 28, 36)

SCREEN = display.set_mode((800, 600))
BACKGROUND = image.load(IMAGE_PATH + 'background.jpg').convert()
FONT = FONT_PATH + 'space_invaders.ttf'
IMG_NAMES = ['ship', 'mystery',
             'enemy1_1', 'enemy1_2',
             'enemy2_1', 'enemy2_2',
             'enemy3_1', 'enemy3_2',
             'explosionblue', 'explosiongreen', 'explosionpurple',
             'laser', 'enemylaser']
IMAGES = {name: image.load(IMAGE_PATH + '{}.png'.format(name)).convert_alpha()
          for name in IMG_NAMES}

BLOCKERS_POSITION = 450
ENEMY_DEFAULT_POSITION = 65  # Initial value for a new game
ENEMY_MOVE_DOWN = 35
EVENT_SHIP_CREATE = USEREVENT + 0
EVENT_ENEMY_SHOOT = USEREVENT + 1
EVENT_ENEMY_MOVE_NOTE = USEREVENT + 2
EVENT_MYSTERY = USEREVENT + 3


class Txt(DirtySprite):
    font_cache = {}
    cache = {}

    def __init__(self, font_, size, msg, color_, x, y, *groups):
        super(Txt, self).__init__(*groups)
        self._x = x
        self._y = y
        self._msg = msg
        self._size = size
        self._font = font_
        self._color = color_
        self.image, self.rect = self.update_image()

    def _get_msg(self):
        return self._msg

    def _set_msg(self, msg):
        if self._msg != msg:
            self._msg = msg
            self.image, self.rect = self.update_image()
            self.dirty = 1

    msg = property(_get_msg, _set_msg, doc="Message Text")

    def update_image(self):
        font_key = hash(self._font) + hash(self._size)
        if font_key in Txt.font_cache:
            font_ = Txt.font_cache[font_key]
        else:
            font_ = font.Font(self._font, self._size)
            Txt.font_cache[font_key] = font_

        key_ = font_key + hash(self.msg) + hash(self._color)
        if key_ in Txt.cache:
            img = Txt.cache[key_]
        else:
            img = font_.render(str(self.msg), True, self._color)
            Txt.cache[key_] = img
        rect = img.get_rect(topleft=(self._x, self._y))
        return img, rect


class Img(DirtySprite):
    cache = {}

    def __init__(self, filename, x=0, y=0, w=0, h=0, *groups):
        super(Img, self).__init__(*groups)
        key_ = hash(filename) + hash(w) + hash(h)
        if key_ in Img.cache:
            self.image = Img.cache[key_]
        else:
            self.image = IMAGES[filename]
            if w > 0 or h > 0:
                self.image = transform.scale(self.image, (w, h))
            Img.cache[key_] = self.image
        self.rect = self.image.get_rect(topleft=(x, y))


class Ship(Img):
    def __init__(self, *groups):
        super(Ship, self).__init__('ship', 375, 540, 0, 0, *groups)
        self.timer = time.get_ticks()

    def update(self, current_time, keys, *args):
        if current_time - self.timer > 20:
            self.timer = current_time
            if keys[K_LEFT] and self.rect.x > 10:
                self.rect.x -= 5
                self.dirty = 1
            if keys[K_RIGHT] and self.rect.x < 740:
                self.rect.x += 5
                self.dirty = 1


class Bullet(Img):
    def __init__(self, x, y, velocity, filename, *groups):
        super(Bullet, self).__init__(filename, x, y, 0, 0, *groups)
        self.velocity = velocity
        self.timer = time.get_ticks()

    def update(self, current_time, *args):
        if current_time - self.timer > 20:
            self.timer = current_time
            self.rect.y += self.velocity
            self.dirty = 1
        if self.rect.y < 15 or self.rect.y > 600:
            self.kill()


class Enemy(DirtySprite):
    row_scores = {0: 30, 1: 20, 2: 20, 3: 10, 4: 10}
    row_images = {
        0: [Img('enemy1_2', w=40, h=35), Img('enemy1_1', w=40, h=35)],
        1: [Img('enemy2_2', w=40, h=35), Img('enemy2_1', w=40, h=35)],
        2: [Img('enemy2_2', w=40, h=35), Img('enemy2_1', w=40, h=35)],
        3: [Img('enemy3_1', w=40, h=35), Img('enemy3_2', w=40, h=35)],
        4: [Img('enemy3_1', w=40, h=35), Img('enemy3_2', w=40, h=35)],
    }

    def __init__(self, x, y, row, column, *groups):
        self.row = row
        self.column = column
        super(Enemy, self).__init__(*groups)
        self.imagesCycle = cycle(Enemy.row_images[self.row])
        self.image = next(self.imagesCycle).image
        self.rect = self.image.get_rect(topleft=(x, y))
        self.score = Enemy.row_scores[self.row]

    def toggle_image(self):
        self.image = next(self.imagesCycle).image
        self.dirty = 1


class EnemiesGroup(Group):
    def __init__(self, columns, rows, position):
        super(EnemiesGroup, self).__init__()
        self.enemies = [[None] * columns for _ in range(rows)]
        self.columns = columns
        self.rows = rows
        self.leftAddMove = 0
        self.rightAddMove = 0
        self.moveTime = 600
        self.direction = 1
        self.rightMoves = 30
        self.leftMoves = 30
        self.moveNumber = 15
        self.timer = time.get_ticks()
        self.bottom = position + (rows - 1) * 45 + 35
        self._aliveColumns = list(range(columns))
        self._leftAliveColumn = 0
        self._rightAliveColumn = columns - 1

    def update(self, current_time):
        if current_time - self.timer > self.moveTime:
            if self.direction == 1:
                max_move = self.rightMoves + self.rightAddMove
            else:
                max_move = self.leftMoves + self.leftAddMove

            if self.moveNumber >= max_move:
                self.leftMoves = 30 + self.rightAddMove
                self.rightMoves = 30 + self.leftAddMove
                self.direction *= -1
                self.moveNumber = 0
                self.bottom = 0
                for enemy in self:
                    enemy.rect.y += ENEMY_MOVE_DOWN
                    enemy.toggle_image()
                    if self.bottom < enemy.rect.y:
                        self.bottom = enemy.rect.y + 35
            else:
                velocity = 10 if self.direction == 1 else -10
                for enemy in self:
                    enemy.rect.x += velocity
                    enemy.toggle_image()
                self.moveNumber += 1
            self.timer += self.moveTime
            event.post(Event(EVENT_ENEMY_MOVE_NOTE, {}))

    def add_internal(self, *sprites):
        super(EnemiesGroup, self).add_internal(*sprites)
        for s in sprites:
            self.enemies[s.row][s.column] = s

    def remove_internal(self, *sprites):
        super(EnemiesGroup, self).remove_internal(*sprites)
        for s in sprites:
            self._kill(s)
        self._update_speed()

    def is_column_dead(self, column):
        return not any(self.enemies[row][column]
                       for row in range(self.rows))

    def random_bottom(self):
        col = choice(self._aliveColumns)
        col_enemies = (self.enemies[row - 1][col]
                       for row in range(self.rows, 0, -1))
        return next((en for en in col_enemies if en is not None), None)

    def _update_speed(self):
        if len(self) == 1:
            self.moveTime = 200
        elif len(self) <= 10:
            self.moveTime = 400

    def _kill(self, enemy):
        self.changed = True
        self.enemies[enemy.row][enemy.column] = None
        is_column_dead = self.is_column_dead(enemy.column)
        if is_column_dead:
            self._aliveColumns.remove(enemy.column)

        if enemy.column == self._rightAliveColumn:
            while self._rightAliveColumn > 0 and is_column_dead:
                self._rightAliveColumn -= 1
                self.rightAddMove += 5
                is_column_dead = self.is_column_dead(self._rightAliveColumn)

        elif enemy.column == self._leftAliveColumn:
            while self._leftAliveColumn < self.columns and is_column_dead:
                self._leftAliveColumn += 1
                self.leftAddMove += 5
                is_column_dead = self.is_column_dead(self._leftAliveColumn)


class Blocker(DirtySprite):
    def __init__(self, x, y, size, color_, *groups):
        super(Blocker, self).__init__(*groups)
        self.image = Surface((size, size))
        self.image.fill(color_)
        self.rect = self.image.get_rect(topleft=(x, y))


class Mystery(Img):
    velocity = 2

    def __init__(self, *groups):
        x = -80 if Mystery.velocity > 0 else 800
        super(Mystery, self).__init__('mystery', x, 45, 75, 35, *groups)
        self.mysteryEntered = Sound(SOUND_PATH + 'mysteryentered.wav')
        self.mysteryEntered.set_volume(0.3)
        self.mysteryEntered.play(fade_ms=1000)
        self.score = choice([50, 100, 150, 300])
        self.timer = time.get_ticks()

    def update(self, current_time, *args):
        if current_time - self.timer > 20:
            self.timer = current_time
            self.rect.x += Mystery.velocity
            self.dirty = 1
            if self.rect.x < -80 or self.rect.x > 800:
                Mystery.velocity *= -1
                self.kill()

    def kill(self):
        super(Mystery, self).kill()
        time.set_timer(EVENT_MYSTERY, 25000)


class EnemyExplosion(Img):
    def __init__(self, enemy, *groups):
        super(EnemyExplosion, self).__init__(
            self.get_image(enemy.row), enemy.rect.x, enemy.rect.y, 40, 35,
            *groups)
        self.image2 = Img(self.get_image(enemy.row), w=50, h=45).image
        self.rect2 = self.image2.get_rect(
            topleft=(enemy.rect.x - 6, enemy.rect.y - 6))
        self.timer = time.get_ticks()

    @staticmethod
    def get_image(row):
        img_colors = ['purple', 'blue', 'blue', 'green', 'green']
        return 'explosion{}'.format(img_colors[row])

    def update(self, current_time, *args):
        passed = current_time - self.timer
        if 100 < passed < 400 and self.image != self.image2:
            self.image = self.image2
            self.rect = self.rect2
            self.dirty = 1
        elif 400 < passed:
            self.kill()


class MysteryExplosion(Txt):
    def __init__(self, mystery, *groups):
        super(MysteryExplosion, self).__init__(
            FONT, 20, mystery.score, WHITE,
            mystery.rect.x + 20, mystery.rect.y + 6,
            *groups)
        self.timer = time.get_ticks()

    def update(self, current_time, *args):
        super(MysteryExplosion, self).update(current_time, *args)
        passed = current_time - self.timer
        if 600 < passed:
            self.kill()
        elif passed <= 200 or 400 < passed <= 600:
            if not self.visible:
                self.visible = True  # dirty = 1
        elif self.visible:
            self.visible = False  # dirty = 1


class ShipExplosion(Img):
    def __init__(self, ship, *groups):
        super(ShipExplosion, self).__init__(
            'ship', ship.rect.x, ship.rect.y, 0, 0, *groups)
        self.timer = time.get_ticks()

    def update(self, current_time, *args):
        passed = current_time - self.timer
        if 900 < passed:
            self.kill()
            event.post(Event(EVENT_SHIP_CREATE, {}))
        elif 300 < passed <= 600 and not self.visible:
            self.visible = True
        elif (passed < 300 or 600 < passed) and self.visible:
            self.visible = False


class EmptyScene(LayeredDirty):
    def __init__(self, *sprites, **kwargs):
        super(EmptyScene, self).__init__(*sprites, **kwargs)
        self.set_timing_treshold(1000.0 / 25.0)
        self.clear(SCREEN, BACKGROUND)
        self.timer = time.get_ticks()
        if DEBUG:
            self.fps = Txt(FONT, 12, "FPS: ", RED, 0, 587, self)

    @staticmethod
    def should_exit(evt):
        # type: (event.EventType) -> bool
        return evt.type == QUIT or (evt.type == KEYUP and evt.key == K_ESCAPE)


class MainScene(EmptyScene):
    def __init__(self, on_key_up, *sprites, **kwargs):
        super(MainScene, self).__init__(*sprites, **kwargs)
        self.on_key_up = on_key_up
        self.add(
            Txt(FONT, 50, 'Space Invaders', WHITE, 164, 155),
            Txt(FONT, 25, 'Press any key to continue', WHITE, 201, 225),
            Img('enemy3_1', 318, 270, 40, 40),
            Txt(FONT, 25, '   =   10 pts', GREEN, 368, 270),
            Img('enemy2_2', 318, 320, 40, 40),
            Txt(FONT, 25, '   =  20 pts', BLUE, 368, 320),
            Img('enemy1_2', 318, 370, 40, 40),
            Txt(FONT, 25, '   =  30 pts', PURPLE, 368, 370),
            Img('mystery', 299, 420, 80, 40),
            Txt(FONT, 25, '   =  ?????', RED, 368, 420),
        )

    def update(self, *args):
        super(MainScene, self).update(*args)
        for e in event.get():
            if self.should_exit(e):
                sys.exit()
            elif e.type == KEYUP:
                self.on_key_up()


class NextRoundScene(EmptyScene):
    def __init__(self, on_finish, *sprites, **kwargs):
        super(NextRoundScene, self).__init__(*sprites, **kwargs)
        self.on_finish = on_finish
        self.add(Txt(FONT, 50, 'Next Round', WHITE, 240, 270))

    def update(self, current_time, *args):
        super(NextRoundScene, self).update(current_time, *args)
        for e in event.get():
            if self.should_exit(e):
                sys.exit()
        passed = current_time - self.timer
        if 3000 < passed:
            self.on_finish()


class GameOverScene(EmptyScene):
    def __init__(self, on_finish, *sprites, **kwargs):
        super(GameOverScene, self).__init__(*sprites, **kwargs)
        self.on_finish = on_finish
        self.gameOverTxt = Txt(FONT, 50, 'Game Over', WHITE, 250, 270, self)

    def update(self, current_time, *args):
        super(GameOverScene, self).update(current_time, *args)
        for e in event.get():
            if self.should_exit(e):
                sys.exit()
        passed = current_time - self.timer
        if 3000 < passed:
            self.on_finish()
        elif passed < 750 or 1500 < passed < 2250:
            if not self.gameOverTxt.visible:
                self.gameOverTxt.visible = True  # dirty = 1
        elif self.gameOverTxt.visible:
            self.gameOverTxt.visible = False  # dirty = 1


class GameScene(EmptyScene):
    def __init__(self, on_round, on_over, *sprites, **kwargs):
        super(GameScene, self).__init__(*sprites, **kwargs)
        self.on_round = on_round
        self.on_over = on_over
        # Init sounds
        self.sounds = {}
        for name in ['shoot', 'shoot2', 'invaderkilled', 'mysterykilled',
                     'shipexplosion']:
            self.sounds[name] = Sound(SOUND_PATH + '{}.wav'.format(name))
            self.sounds[name].set_volume(0.2)
        # Init notes
        self.musicNotes = [Sound(SOUND_PATH + '{}.wav'.format(i))
                           for i in range(4)]
        for note in self.musicNotes:
            note.set_volume(0.5)
        self.musicNotesCycle = cycle(self.musicNotes)

        # Counter for enemy starting position (increased each new round)
        self.enemyPosition = ENEMY_DEFAULT_POSITION
        self.bullets = Group()
        self.enemyBullets = Group()
        self.explosions = Group()
        self.players = Group()
        self.mysteries = Group()
        self.allBlockers = Group()

        self.dashGroup = Group(Txt(FONT, 20, 'Score', WHITE, 5, 5),
                               Txt(FONT, 20, 'Lives ', WHITE, 640, 5))
        self.scoreTxt = Txt(FONT, 20, 0, GREEN, 85, 5, self.dashGroup)
        self.life1 = Img('ship', 715, 3, 23, 23, self.dashGroup)
        self.life2 = Img('ship', 742, 3, 23, 23, self.dashGroup)
        self.life3 = Img('ship', 769, 3, 23, 23, self.dashGroup)

    def make_blockers(self):
        for offset in (50, 250, 450, 650):
            for row in range(4):
                for column in range(9):
                    x = offset + (column * 10)
                    y = BLOCKERS_POSITION + (row * 10)
                    Blocker(x, y, 10, GREEN, self.allBlockers)

    def make_enemies(self):
        self.enemies = EnemiesGroup(10, 5, self.enemyPosition)
        for row in range(5):
            for col in range(10):
                x = 154 + (col * 50)
                y = self.enemyPosition + (row * 45)
                Enemy(x, y, row, col, self.enemies, self)

    def reset(self):
        for gr in (self, self.players, self.explosions, self.mysteries,
                   self.bullets, self.enemyBullets):
            gr.empty()
        if DEBUG:
            self.add(self.fps)
        self.add(self.dashGroup, self.allBlockers)
        self.player = Ship(self, self.players)
        self.make_enemies()
        event.clear()
        time.set_timer(EVENT_ENEMY_SHOOT, 700)
        time.set_timer(EVENT_MYSTERY, 25000)

    def check_input(self):
        for e in event.get():
            if self.should_exit(e):
                sys.exit()
            elif e.type == KEYDOWN:
                if e.key == K_SPACE:
                    if not self.bullets and self.player.alive():
                        y = self.player.rect.y + 5
                        if self.scoreTxt.msg < 1000:
                            Bullet(self.player.rect.x + 23, y, -15, 'laser',
                                   self.bullets, self)
                            self.sounds['shoot'].play()
                        else:
                            Bullet(self.player.rect.x + 8, y, -15, 'laser',
                                   self.bullets, self)
                            Bullet(self.player.rect.x + 38, y, -15, 'laser',
                                   self.bullets, self)
                            self.sounds['shoot2'].play()
            elif e.type == EVENT_SHIP_CREATE:
                self.player = Ship(self, self.players)
            elif e.type == EVENT_ENEMY_SHOOT and self.enemies:
                enemy = self.enemies.random_bottom()
                Bullet(enemy.rect.x + 14, enemy.rect.y + 20, 5, 'enemylaser',
                       self.enemyBullets, self)
            elif e.type == EVENT_ENEMY_MOVE_NOTE:
                next(self.musicNotesCycle).play()
            elif e.type == EVENT_MYSTERY:
                Mystery(self.mysteries, self)

    def check_collisions(self):
        groupcollide(self.bullets, self.enemyBullets, True, True)

        for enemy in groupcollide(self.enemies, self.bullets,
                                  True, True).keys():
            self.sounds['invaderkilled'].play()
            self.scoreTxt.msg += enemy.score
            EnemyExplosion(enemy, self.explosions, self)

        for mystery in groupcollide(self.mysteries, self.bullets,
                                    True, True).keys():
            mystery.mysteryEntered.stop()
            self.sounds['mysterykilled'].play()
            self.scoreTxt.msg += mystery.score
            MysteryExplosion(mystery, self.explosions, self)
            Mystery.velocity = 2  # Reset direction

        for playerShip in groupcollide(self.players, self.enemyBullets,
                                       True, True).keys():
            if self.life3.alive():
                self.life3.kill()
            elif self.life2.alive():
                self.life2.kill()
            elif self.life1.alive():
                self.life1.kill()
            else:
                self.on_over()
            self.sounds['shipexplosion'].play()
            ShipExplosion(playerShip, self.explosions, self)

        if self.enemies.bottom >= 540:
            groupcollide(self.enemies, self.players, True, True)
            if not self.player.alive() or self.enemies.bottom >= 600:
                self.on_over()

        groupcollide(self.bullets, self.allBlockers, True, True)
        groupcollide(self.enemyBullets, self.allBlockers, True, True)
        if self.enemies.bottom >= BLOCKERS_POSITION:
            groupcollide(self.enemies, self.allBlockers, False, True)

    def update(self, current_time, *args):
        if any((self.enemies, self.explosions,
                self.mysteries, self.enemyBullets)):
            self.enemies.update(current_time)
            self.check_input()
            self.check_collisions()
        else:
            self.on_round()
        super(GameScene, self).update(current_time, *args)

    def new_game(self):
        # Reset enemy start position
        self.enemyPosition = ENEMY_DEFAULT_POSITION
        # Only create blockers on a new game, not a new round
        self.allBlockers.empty()
        self.make_blockers()
        self.scoreTxt.msg = 0
        self.dashGroup.add(self.life1, self.life2, self.life3)
        self.reset()

    def new_round(self):
        # Move enemies closer to bottom
        self.enemyPosition += ENEMY_MOVE_DOWN
        self.reset()


class SpaceInvaders(object):
    def __init__(self):
        # It seems, in Linux buffersize=512 is not enough, use 4096 to prevent:
        #   ALSA lib pcm.c:7963:(snd_pcm_recover) underrun occurred
        mixer.pre_init(44100, -16, 1, 4096)
        init()
        self.caption = display.set_caption('Space Invaders')

        self.mainScene = MainScene(on_key_up=self.start_game)
        self.gameScene = GameScene(on_round=self.show_round,
                                   on_over=self.show_over)
        self.clock = time.Clock()
        self.scene = self.mainScene

    def start_game(self):
        self.gameScene.new_game()
        self.scene = self.gameScene
        self.scene.repaint_rect(SCREEN.get_rect())

    def start_round(self):
        self.gameScene.new_round()
        self.scene = self.gameScene
        self.scene.repaint_rect(SCREEN.get_rect())

    def show_round(self):
        self.scene = NextRoundScene(on_finish=self.start_round)
        self.scene.add(self.gameScene.dashGroup)

    def show_over(self):
        self.scene = GameOverScene(on_finish=self.show_main)
        self.scene.add(self.gameScene.dashGroup)

    def show_main(self):
        self.scene = self.mainScene
        self.scene.repaint_rect(SCREEN.get_rect())

    def main(self):
        while True:
            # Update all the sprites
            current_time = time.get_ticks()
            keys = key.get_pressed()
            if DEBUG:
                self.scene.fps.msg = "FPS: " + str(int(self.clock.get_fps()))
            self.scene.update(current_time, keys)

            # Draw the scene
            dirty = self.scene.draw(SCREEN)
            display.update(dirty)
            self.clock.tick(60)


if __name__ == '__main__':
    game = SpaceInvaders()
    game.main()
