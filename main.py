import random
import functools
import math
import threading
import time
import cPickle as pickle
import os
import datetime
import pytz
uspac = pytz.timezone("US/Pacific")

import kivy
kivy.require('1.8.0')

__version__ = '0.3.2'

def get_user_path():
    """ Return the folder to where user data can be stored """
    root = os.getenv('EXTERNAL_STORAGE') or os.path.expanduser("~")
    path = os.path.join(root, ".SlideWords")
    if not os.path.exists(path):
        os.makedirs(path)
    return path

import colors

#from kivy.uix.listview import ListView, ListItemLabel, ListItemButton
from kivy.adapters.listadapter import ListAdapter
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scatterlayout import ScatterLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty, ReferenceListProperty, NumericProperty, \
    BooleanProperty, ListProperty, ObjectProperty, DictProperty
from kivy.uix.image import Image
from kivy.graphics.texture import Texture
from kivy.graphics import Rectangle, Color
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.vector import Vector
from kivy.animation import Animation
from kivy.logger import Logger
from kivy.storage.jsonstore import JsonStore
from kivy.utils import platform
from globals import words, board_size, tiles
from players import Player, AIPlayer, player_types

platform = platform()
if platform == 'android':
    # Support for Google Play
    import googleplaysettings
    import googleplayservices
    leaderboard_highscore = 'high_score'
    leaderboard_daily_challenge_highscore = 'daily_challenge_high_score'
    leaderboard_1000_games = 'number_1000_plus_games'
    googleplayclient = googleplayservices.GoogleClient()
#    from kivy.uix.popup import Popup
    from kivy.uix.popup import Popup
    class GooglePlayPopup(Popup):
        pass


class Tile(Widget):
    letter = StringProperty('A')
    value = NumericProperty()
    selected = BooleanProperty(False)
    gpos_x = NumericProperty()
    gpos_y = NumericProperty()
    gpos = ReferenceListProperty(gpos_x, gpos_y)
    opos_x = NumericProperty()
    opos_y = NumericProperty()
    opos = ReferenceListProperty(opos_x, opos_y)
    cpos_x = NumericProperty()
    cpos_y = NumericProperty()
    cpos = ReferenceListProperty(cpos_x, cpos_y)
    w_label = ObjectProperty()
    def __init__(self, board, x, y, letter, value):
        super(Tile,self).__init__()
        self.letter = letter
        self.value = value
        self.gpos_x = x
        self.gpos_y = y
        self.opos = self.gpos
        self.cpos = self.gpos
        self.board = board
        self.bind(gpos = self.gpos_changed)

    def gpos_changed(self, *args):
        if not self.board.block_gpos_updates:
            del self.board[self.cpos]
            if tuple(self.gpos) != (-1, -1):
                self.board[self.gpos] = self
        self.cpos = self.gpos
        a = Animation(pos = self.board.gpos2pos(self.gpos), duration = 0.25)
        a.start(self)

    def on_touch_down(self, touch):
        if not self.board.active_player.local_touch():
            return
        if self.board.block_gpos_updates:
            return False
        if self.collide_point(*touch.pos):
            if self.selected:
                self.board.reset_selected()
            else:
                self.candidates = self.board.get_move_candidates(self)
                if len(self.candidates)>0:
                    touch.grab(self)
                    self.board.draw_background(self.candidates)
                    self.pos_offset = touch.pos[0] - self.pos[0], touch.pos[1] - self.pos[1]
            return True

    def on_touch_move(self, touch):
        if not self.board.active_player.local_touch():
            return
        if touch.grab_current is self:
            self.pos[0] = touch.pos[0] - self.pos_offset[0]
            self.pos[1] = touch.pos[1] - self.pos_offset[1]
            return True

    def on_touch_up(self, touch):
        if not self.board.active_player.local_touch():
            return
        if touch.grab_current is self:
            gpos = self.board.pos2gpos(touch.pos)
            if gpos in self.candidates:
                self.board.select(self, gpos)
            else:
                self.gpos = self.opos
            self.pos = self.board.gpos2pos(self.gpos)
            touch.ungrab(self)
            self.board.draw_background()
            return True

class Board(FloatLayout):
    game_over = BooleanProperty()
    def __init__(self,**kwargs):
        super(Board,self).__init__(**kwargs)
        self.scorebar = ScoreBar()
        self.wordbar = WordBar()
        self.messagebar = MessageBar()
        self.scorebar.bind(game_id = self.messagebar.game_changed)
        self.scorebar.bind(players = self.messagebar.active_player_changed)
        self.scorebar.bind(score = self.update_pass_bar)
        self.scorebar.bind(score_2 = self.update_pass_bar)
        self.scorebar.bind(active_player = self.messagebar.active_player_changed)
        self.scorebar.bind(on_touch_down = self.on_touch_score)
        self.wordbar.w_word_label.bind(on_touch_down = self.confirm_word)
        self.bind(size = self.size_changed)
        self.bind(game_over = self.messagebar.game_over)
        self.menu = Menu()
        self.menu.bind(selection = self.menu_choice)
        self.multiplayer_menu = MultiplayerMenu()
        self.multiplayer_menu.bind(selection = self.menu_choice)
        self.leaderboard_menu = LeaderboardMenu()
        self.leaderboard_menu.bind(selection = self.menu_choice)
        self.tiles = {}
        self.selection = []
        self.add_widget(self.scorebar)
        self.add_widget(self.wordbar)
        self.add_widget(self.messagebar)
        self.block_gpos_updates = False
        self.instructions = Instructions()
        self.players = {1: Player(self, 1)}
        self.score_detail_1p = ScoreDetail1p()
        self.score_detail_2p = ScoreDetail2p(self.players)
        self.active_player = self.players[1]
        self.game_over = False
        self.consecutive_passes = 0

        tile_set = []
        for t in tiles:
            tile_set += [(t[0],t[1]+1)]*t[2]

        self.initial_tile_positions = []
        self.original_gps = self.initial_tile_positions[:]
        for x in range(board_size):
            for y in range(board_size):
                if x in [board_size//2-1,board_size//2] and y in [board_size//2-1,board_size//2]:
                    continue
                self.initial_tile_positions.append((x,y))

        self.tile_widgets = []
        for (x,y),(l,v) in zip(self.initial_tile_positions, tile_set):
            t = Tile(self, -1, -1, l, v)
            self.add_widget(t)
            self.tile_widgets.append(t)

        self.first_start = True
        self.ai = AIPlayer(self, 2)

    def overlay_showing(self):
        return self.menu in self.children \
            or self.multiplayer_menu in self.children \
            or self.leaderboard_menu in self.children \
            or self.instructions in self.children \
            or self.score_detail_1p in self.children \
            or self.score_detail_2p in self.children

    def show_menu(self):
        self.menu.selection = -1
        self.add_widget(self.menu)

    def hide_menu(self):
        self.remove_widget(self.menu)
        self.hide_multiplayer_menu()
        self.hide_leaderboard_menu()

    def show_multiplayer_menu(self):
        self.multiplayer_menu.selection = -1
        self.add_widget(self.multiplayer_menu)

    def hide_multiplayer_menu(self):
        try:
            self.remove_widget(self.multiplayer_menu)
        except:
            pass

    def show_leaderboard_menu(self):
        self.leaderboard_menu.selection = -1
        self.add_widget(self.leaderboard_menu)

    def hide_leaderboard_menu(self):
        try:
            self.remove_widget(self.leaderboard_menu)
        except:
            pass

    def menu_choice(self, menu, selection):
        if selection == 1:
            self.hide_menu()
            self.restart_game()
        if selection == 2:
            self.hide_menu()
            self.new_game()
        if selection == 3:
            self.hide_menu()
            self.new_daily_game()
        if selection == 4:
            self.hide_menu()
            self.show_multiplayer_menu()
        if selection == 5:
            self.hide_menu()
            self.add_widget(self.instructions)
        if selection == 6:
            self.hide_menu()
            self.show_leaderboard_menu()
        if selection == 7:
            self.hide_menu()
            if platform == 'android':
                App.get_running_app().gs_show_achievements()
        if selection == 8:
            App.get_running_app().set_next_theme()
            self.hide_menu()
            self.show_menu()
        if selection == 9:
            App.get_running_app().stop()
        if selection == 10:
            self.hide_multiplayer_menu()
            self.new_multiplayer_game()
        if selection == 11:
            if self.multiplayer_menu.player1 < len(player_types):
                self.multiplayer_menu.player1 += 1
            else:
                self.multiplayer_menu.player1 = 1
            self.hide_multiplayer_menu()
            self.show_multiplayer_menu()
        if selection == 12:
            if self.multiplayer_menu.player2 < len(player_types):
                self.multiplayer_menu.player2 += 1
            else:
                self.multiplayer_menu.player2 = 1
            self.hide_multiplayer_menu()
            self.show_multiplayer_menu()
        if selection == 13:
            if platform == 'android':
                score_type = leaderboard_highscore
                App.get_running_app().gs_show_leaderboard(score_type)
        if selection == 14:
            if platform == 'android':
                score_type = leaderboard_daily_challenge_highscore
                App.get_running_app().gs_show_leaderboard(score_type)
        if selection == 15:
            if platform == 'android':
                score_type = leaderboard_1000_games
                App.get_running_app().gs_show_leaderboard(score_type)


    def pos2gpos(self, pos):
        return int((pos[0] - self.off_x)//self.tile_space_size), int((pos[1] - self.off_y)//self.tile_space_size)

    def new_game(self):
        self.active_player.abort()
        self.original_gps = [gp for gp in self.initial_tile_positions]
        random.seed()
        random.shuffle(self.original_gps)
        self.players.clear()
        self.players[1] = Player(self, 1)
        self.active_player = self.players[1]
        self.scorebar.set_game_id()
        self.reset()

    def new_daily_game(self):
        self.active_player.abort()
        date = uspac.fromutc(datetime.datetime.utcnow())
        seed = date.year*10000+date.month*100+date.day
        random.seed(seed)
        self.original_gps = [gp for gp in self.initial_tile_positions]
        random.shuffle(self.original_gps)
        game_id = 'd%i%i%i'%(date.year, date.month, date.day)
        self.players.clear()
        self.players[1] = Player(self, 1)
        self.active_player = self.players[1]
        self.scorebar.set_game_id(game_id)
        self.reset()

    def new_multiplayer_game(self):
        self.active_player.abort()
        self.original_gps = [gp for gp in self.initial_tile_positions]
        random.seed()
        random.shuffle(self.original_gps)
        p1 = player_types[self.multiplayer_menu.player1](self, 1)
        p2 = player_types[self.multiplayer_menu.player2](self, 2)
        self.players.clear()
        self.players[1] = p1
        self.players[2] = p2
        self.active_player = self.players[1]
        self.scorebar.set_game_id('', multiplayer = True)
        self.reset()

    def restart_game(self):
        self.active_player.abort()
        self.active_player = self.players[1]
        self.scorebar.active_player = 1
        for p in self.players:
            self.players[p].reset()
        self.reset()

    def reset(self):
        Clock.schedule_once(lambda *args: self.reset_tick(0), 0.01)
        self.game_over = False
        self.consecutive_passes = 0
        self.scorebar.score = 0
        self.scorebar.score_2 = 0
        self.wordbar.word = ''
        self.wordbar.word_score = 0
        self.selection = []
        self.score_detail_1p.reset()
        self.score_detail_2p.reset()

    def reset_tick(self, i):
        if i==0:
            self.block_gpos_updates = True
            self.tiles = {}
        anim_count = 5
        anim_ind = min(len(self.tile_widgets), i + anim_count)
        j=i
        while j < anim_ind:
            t  = self.tile_widgets[j]
            gp = self.original_gps[j]
            t.opos = gp
            t.cpos = gp
            t.gpos = gp
            t.selected = False
            self[t.gpos] = t
            j += 1
        if j < len(self.tile_widgets):
            Clock.schedule_once(lambda *args: self.reset_tick(j), 0.01*(j-i))
        else:
            self.block_gpos_updates = False
            Clock.schedule_once(lambda *args: self.active_player.start_turn(), 0.25)

    def gpos2pos(self, gpos):
        if tuple(gpos) == (-1, -1):
            return self.size[0]/2, self.size[1]
        else:
            return self.off_x + self.tile_space_size*gpos[0], self.off_y + self.tile_space_size*gpos[1]

    def _conv_pos(self, gpos):
        return int(gpos[0]), int(gpos[1])

    def __getitem__(self, gpos):
        return self.tiles[self._conv_pos(gpos)]

    def __setitem__(self, gpos, value):
        self.tiles[self._conv_pos(gpos)] = value

    def __delitem__(self, gpos):
        del self.tiles[self._conv_pos(gpos)]

    def __contains__(self, gpos):
        return self._conv_pos(gpos) in self.tiles

    def size_changed(self,*args):
        self.tile_space_size = min(self.size[0], 0.8*self.size[1])//board_size
        self.tile_size = self.tile_space_size-2
        self.board_size = board_size*self.tile_space_size
        self.off_x = (self.size[0] - self.board_size)/2
        self.off_y = 0.9*self.size[1] - self.board_size
        self.wordbar.size = (self.size[0]*3/4, 0.06*self.size[1])
        self.wordbar.pos = (self.size[0]/8, 0.04*self.size[1] + (self.off_y - 0.04*self.size[1] - 0.06*self.size[1])/2)
        self.messagebar.size = (self.size[0], 0.04*self.size[1])
        self.messagebar.pos = (0, 0)
        self.scorebar.size = (self.size[0],0.1*self.size[1])
        self.scorebar.pos = (0, 0.9*self.size[1])
        for t in self.tile_widgets:
            t.pos = self.gpos2pos(t.gpos)
            t.size = (self.tile_size, self.tile_size)
        #draw a checkerboard to make it easier to see sliding positions
        self.menu.size = self.size
        self.menu.pos = self.pos
        self.multiplayer_menu.size = self.size
        self.multiplayer_menu.pos = self.pos
        self.leaderboard_menu.size = self.size
        self.leaderboard_menu.pos = self.pos
        self.instructions.size = self.size
        self.instructions.pos = self.pos
        self.score_detail_1p.size = self.size
        self.score_detail_1p.pos = self.pos
        self.score_detail_2p.size = self.size
        self.score_detail_2p.pos = self.pos
        self.draw_background()
        if self.first_start:
            self.first_start = False
            try:
                if not self.load_state():
                    self.new_game()
            except:
                self.new_game()

    def draw_background(self, candidates = None):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*colors.background)
            Rectangle(pos = self.pos, size = self.size)
            Color(*colors.checker)
            for x in range(board_size):
                for y in range(board_size):
                    if (x+y)%2 == 0:
                        Rectangle(pos = (self.off_x + x*self.tile_space_size, self.off_y + y*self.tile_space_size), size = (self.tile_size, self.tile_size))
            if candidates is not None:
                Color(*colors.move_candidates)
                for c in candidates:
                    x, y = c
                    Rectangle(pos = (self.off_x + x*self.tile_space_size + self.tile_space_size/4, self.off_y + y*self.tile_space_size + self.tile_space_size/4), size = (self.tile_size/2, self.tile_size/2))

    def select(self, tile, gpos):
        tile.gpos = gpos
        self.selection.append(self._conv_pos(tile.gpos))
        tile.selected = True
        self.update_word_bar()
        return True

    def update_word_bar(self):
        self.update_pass_bar()
        self.wordbar.word, self.wordbar.word_score = self.is_selection_a_word()

    def update_pass_bar(self, *args):
        self.wordbar.can_pass = self.selection == [] and self.active_player.local_touch()

    def reset_selected(self):
        # this has a bug if user moves more than one tile
        self.block_gpos_updates = True
        for gp in self.selection:
            del self[gp]
        for t in self.tile_widgets:
            if t.selected:
                t.gpos = t.opos
                t.selected = False
                self[t.gpos] = t
        self.block_gpos_updates = False
        self.wordbar.word = ''
        self.wordbar.word_score = 0
        self.selection = []
        self.update_pass_bar()

    def show_move_candidates(self, tile):
        candidates = self.get_move_candidates(tile)
        self.draw_background(candidates)
        return candidates

    def get_move_candidates(self, tile):
        '''
        returns a list containing the positions of all valid moves for this `tile`
        if there is a selection, the list of positions will be in line with the selection
        '''
        candidates = [(tile.gpos[0], tile.gpos[1])]
        for direction in ([-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]):
            gp = tile.gpos[0] + direction[0], tile.gpos[1] + direction[1]
            while 0<=gp[0]<board_size and 0<=gp[1]<board_size:
                if gp not in self:
                    candidates.append(gp)
                else:
                    break
                gp = gp[0]+direction[0], gp[1]+direction[1]
        sel_candidates = self.get_selection_line_candidates()
        if sel_candidates is not None:
            icandidates = []
            for c in candidates:
                if c in sel_candidates:
                    icandidates.append(c)
            return icandidates
        else:
            return candidates

    def get_selection_line_candidates(self):
        candidates = []
        if len(self.selection) == 0:
            return None
        if len(self.selection) == 1:
            s = self.selection[0]
            for direction in ([-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]):
                gp = s[0] + direction[0], s[1] + direction[1]
                while 0<=gp[0]<board_size and 0<=gp[1]<board_size:
                    candidates.append(gp)
                    gp = gp[0]+direction[0], gp[1]+direction[1]
            return candidates
        if len(self.selection) >= 2:
            start = self.selection[0]
            end = self.selection[-1]
            dist = start[0] - end[0], start[1] - end[1]
            dx = int(dist[0]>0) - int(dist[0]<0)
            dy = int(dist[1]>0) - int(dist[1]<0)
            for dx,dy in ((dx,dy),(-dx,-dy)):
                gp = start[:]
                while 0<=gp[0]<board_size and 0<=gp[1]<board_size:
                    candidates.append(gp)
                    gp = gp[0]+dx, gp[1]+dy
            return candidates

    def is_selection_a_word(self):
        has_move = False
        sum_value = 0
        sel = sorted(self.selection)
        candidate = ''
        start = sel[0]
        end = sel[-1]
        dist = end[0] - start[0], end[1] - start[1]
        dx = int(dist[0]>0) - int(dist[0]<0)
        dy = int(dist[1]>0) - int(dist[1]<0)
        for s,n in zip(sel, range(len(sel))):
            if s != (sel[0][0]+n*dx, sel[0][1]+n*dy):
                return '', 0
            t = self[s]
            candidate += t.letter
            sum_value += t.value
            has_move = has_move or t.gpos != t.opos
        if not has_move:
            return '', 0
        if candidate in words:
            return candidate, sum_value*len(candidate)
        if candidate[::-1] in words:
            return candidate[::-1], sum_value*len(candidate)
        return '', 0

    def confirm_word(self, widget, touch):
        if not self.active_player.local_touch():
            return
        if not widget.collide_point(*touch.pos):
            return
        self.end_turn()

    def end_turn(self):
        pass_turn = self.selection == []
        word = str(self.wordbar.word)
        score = int(self.wordbar.word_score)
        if pass_turn:
            self.consecutive_passes += 1
        else:
            self.consecutive_passes = 0
            if platform == 'android' and self.scorebar.players == 1:
                ws = self.wordbar.word_score
                word = self.wordbar.word
                if len(word) >= 3:
                    if len(word) >= 9:
                        App.get_running_app().gs_achieve('achievement_%i_letter_word'%(len(word),))
                    else:
                        App.get_running_app().gs_inc_achieve('achievement_%i_letter_word'%(len(word),))            
        if self.scorebar.active_player == 1:
            self.scorebar.score += self.wordbar.word_score
        else:
            self.scorebar.score_2 += self.wordbar.word_score
        if platform == 'android' and self.scorebar.players == 1 and score<1000<=self.scorebar.score and self.scorebar.score>=1000:
            App.get_running_app().gs_get_score(leaderboard_1000_games)
            if self.score_bar.score > self.scorebar.hi_score:
                if self.game_id != 'default':
                    App.get_running_app().gs_score(leaderboard_daily_challenge_highscore, int(self.score))
                App.get_running_app().gs_score(leaderboard_highscore, int(self.score))
        self.wordbar.word = ''
        self.wordbar.word_score = 0
        for s in self.selection:
            t = self[s]
            t.selected = False
            t.gpos = (-1, -1)
        self.selection = []
        if self.scorebar.players == 2:
            self.score_detail_2p.add(self.scorebar.active_player, word, score)
        else:
            self.score_detail_1p.add(word, score)
        if self.consecutive_passes == self.scorebar.players:
            self.game_over = True
            self.wordbar.can_pass = False
            self.score_detail_1p.title = 'Game Over'
            self.score_detail_2p.title = 'Game Over'
            self.show_score_summary()
        else:
            if self.scorebar.players == 2:
                self.scorebar.active_player = 3 - self.scorebar.active_player
                self.active_player = self.players[self.scorebar.active_player]
            self.update_pass_bar()
            self.active_player.start_turn()

    def update_1000_games_tally(self, score):
        if score>=0:
            App.get_running_app().gs_score(leaderboard_1000_games, score + 1)

    def on_touch_score(self, scorebar, touch):
        if self.scorebar.collide_point(*touch.pos):
            self.show_score_summary()
        return True
                
    def show_score_summary(self):
        if self.overlay_showing():
            return
        if len(self.players) == 2:
            self.add_widget(self.score_detail_2p)
        else:
            self.add_widget(self.score_detail_1p)

    def path_state(self):
        return os.path.join(get_user_path(),'gamestate.pickle')

    def load_state(self):
        path = self.path_state()
        if not os.path.exists (path):
            return False
        Logger.info ('loading game data')
        store = file(path,'rb')
        game = pickle.loads (store.read ())
        grid_data = game['grid_data']
        self.original_gps = game['original_gps']
        try:
            self.scorebar.players = game['players']
        except:
            self.scorebar.players = 1
        if self.scorebar.players == 1:
            self.selection = game['selection']
            self.wordbar.word_score = game['word_score']
            self.wordbar.word = game['word']
            self.scorebar.set_game_id(game['high_score_id'])
            self.scorebar.score = game['score']
            self.scorebar.active_player = 1
            self.players.clear()
            self.players[1] = Player(self, 1)
            try:
                self.score_detail_1p.set_score_data(game['score_data'])
            except:
                pass
        else:
            self.selection = []
            self.wordbar.word_score = 0
            self.wordbar.word = ''
            self.scorebar.score = game['score']
            self.scorebar.score_2 = game['score_2']
            self.scorebar.active_player = game['active_player']
            p1type, p2type = game['ptypes']
            self.players.clear()
            self.players[1] = player_types[p1type](self,1)
            self.players[2] = player_types[p2type](self,2)
            self.score_detail_2p.set_score_data(game['score_data1'], game['score_data2'])

        self.block_gpos_updates = True
        self.tiles = {}

        for t,gd in zip(self.tile_widgets,grid_data):
            letter, value, selected, gpos, cpos, opos = gd
            t.letter = letter
            t.value = value
            t.cpos = cpos
            t.opos = opos
            t.gpos = gpos
            if self.scorebar.players == 1:
                t.selected = selected
            self[t.gpos] = t

        store.close ()
#        os.remove(path)
        self.active_player = self.players[self.scorebar.active_player]
        if self.scorebar.players == 2:
            self.active_player.start_turn()
        self.block_gpos_updates = False
        
        return True

    def save_state(self):
        if self.game_over:
            if os.path.exists(self.path_state()):
                os.remove(self.path_state())
            return
        grid_data = []
        for t in self.tile_widgets:
            grid_data.append((str(t.letter), int(t.value), bool(t.selected), tuple(t.gpos), tuple(t.cpos), tuple(t.opos)))

        store = file(self.path_state(),'wb')
        if self.scorebar.players == 1:
            data = dict(
                version = __version__,
                grid_data = grid_data,
                original_gps = self.original_gps,
                selection = self.selection,
                word = self.wordbar.word,
                word_score = self.wordbar.word_score,
                high_score_id = self.scorebar.game_id,
                players = self.scorebar.players,
                score = self.scorebar.score,
                score_data = self.score_detail_1p.score_data
                )
        else:
            data = dict(
                version = __version__,
                grid_data = grid_data,
                original_gps = self.original_gps,
                selection = self.selection,
                word = self.wordbar.word,
                word_score = self.wordbar.word_score,
                players = self.scorebar.players,
                active_player = self.scorebar.active_player,
                score = self.scorebar.score,
                score_2 = self.scorebar.score_2,
                score_data1 = self.score_detail_2p.score_data1,
                score_data2 = self.score_detail_2p.score_data2,
                ptypes = (self.players[1].type, self.players[2].type)
                )
        store.write(pickle.dumps(data))
        store.close()
        Logger.info ('saved game data')

class Instructions(BoxLayout):
    m_scrollview = ObjectProperty()
    def __init__(self):
        super(Instructions,self).__init__()

class ScoreDetail1p(BoxLayout):
    detail = StringProperty()
    title = StringProperty()
    def __init__(self):
        super(ScoreDetail1p,self).__init__()
        self.reset()
    def reset(self):
        self.score_data = []
        self.title = 'Start of the Game'
        self.detail ='SCORE: 0'
    def set_score_data(self, score_data):
        self.score_data = score_data
        self.update_text()
    def add(self, word, score):
        if word == '' and score == 0:
            word = '<PASS>'
        self.score_data.append((word,score))
        self.update_text()
    def update_text(self):
        self.title = 'Turn %i'%(len(self.score_data)+1)
        total = sum(s[1] for s in self.score_data)
        detail = 'SCORE: %i\n\n'%total
        detail += '\n'.join(['%i %s'%(s,w) for w,s in self.score_data])
        self.detail = detail


class ScoreDetail2p(BoxLayout):
    detail1 = StringProperty()
    detail2 = StringProperty()
    title = StringProperty()
    def __init__(self, players):
        super(ScoreDetail2p,self).__init__()
        self.players = players
        self.reset()
    def reset(self):
        self.score_data1 = []
        self.score_data2 = []
        self.title = 'Start of the Game'
        name = self.players[1].name
        pname1 = name if name!='HUMAN' else 'PLAYER 1'
        name = self.players[2].name if len(self.players)==2 else ''
        pname2 = name if name!='HUMAN' else 'PLAYER 2'
        pname2 = 'PLAYER 2'
        self.detail1 ='%s: 0'%(pname1,)
        self.detail2 ='%s: 0'%(pname2,)
    def set_score_data(self, score_data1, score_data2):
        self.score_data1 = score_data1
        self.score_data2 = score_data2
        self.update_text()
    def add(self, player, word, score):
        if word == '' and score == 0:
            word = '<PASS>'
        if player == 1:
            self.score_data1.append((word,score))
        elif player == 2:
            self.score_data2.append((word,score))
        self.update_text()
    def update_text(self):
        self.title = 'Turn %i'%(len(self.score_data2)+1)
        total = sum(s[1] for s in self.score_data1)
        name = self.players[1].name
        pname1 = name if name!='HUMAN' else 'PLAYER 1'
        detail = '%s: %i\n\n'%(pname1,total)
        detail += '\n'.join(['%i %s'%(s,w) for w,s in self.score_data1])
        self.detail1 = detail
        total = sum(s[1] for s in self.score_data2)
        name = self.players[2].name if len(self.players)==2 else ''
        pname2 = name if name!='HUMAN' else 'PLAYER 2'
        detail = '%s: %i\n\n'%(pname2,total)
        detail += '\n'.join(['%s %i'%(w,s) for w,s in self.score_data2])
        self.detail2 = detail


class Menu(BoxLayout):
    selection = NumericProperty(-1)
    def __init__(self):
        super(Menu,self).__init__()

    def on_touch_down(self, touch):
        return True
        for c in self.children:
            if c.collide_point(*touch.pos):
                return True

    def on_touch_up(self, touch):
        for c in self.children:
            if c.collide_point(*touch.pos):
                self.selection = c.value
                return True

class MultiplayerMenu(BoxLayout):
    selection = NumericProperty(-1)
    player1 = NumericProperty()
    player2 = NumericProperty()
    players = ListProperty()
    def __init__(self):
        super(MultiplayerMenu,self).__init__()
        self.players = [''] + [p.name for p in player_types.itervalues()]
        
    def on_touch_down(self, touch):
        return True
        for c in self.children:
            if c.collide_point(*touch.pos):
                return True

    def on_touch_up(self, touch):
        for c in self.children:
            if c.collide_point(*touch.pos):
                self.selection = c.value
                return True

class LeaderboardMenu(BoxLayout):
    selection = NumericProperty(-1)
    def __init__(self):
        super(LeaderboardMenu,self).__init__()
        self.players = [''] + [p.name for p in player_types.itervalues()]
        
    def on_touch_down(self, touch):
        return True
        for c in self.children:
            if c.collide_point(*touch.pos):
                return True

    def on_touch_up(self, touch):
        for c in self.children:
            if c.collide_point(*touch.pos):
                self.selection = c.value
                return True

class ScoreBar(BoxLayout):
    score = NumericProperty()
    hi_score = NumericProperty()
    game_id = StringProperty()
    players = NumericProperty()
    active_player = NumericProperty()

    def __init__(self,**kwargs):
        super(ScoreBar,self).__init__(**kwargs)
        self.store = JsonStore(os.path.join(get_user_path(),'scores.json'))
        self.bind(score = self.score_changed)
        self.set_game_id()

    def set_game_id(self, game_id = 'default', multiplayer = False):
        self.players = int(multiplayer) + 1
        self.active_player = 1
        self.game_id = game_id
        if self.players == 1:
            if self.store.exists(game_id):
                data = self.store.get(game_id)
                self.hi_score = data['high_score']
            else:
                self.hi_score = 0

    def score_changed(self, *args):
        if self.players == 2:
            return
        if self.game_id != 'default':
            date = uspac.fromutc(datetime.datetime.utcnow())
            game_id = 'd%i%i%i'%(date.year, date.month, date.day)
            if self.game_id != game_id:
                #daily challenge has finished, the game reverts to default type so we only update the default high score table
                self.set_game_id()
            else:
                #store the high score in the default table as well as in the daily table
                hi_score = 0
                if self.store.exists('default'):
                    data = self.store.get('default')
                    hi_score = data['high_score']
                if self.score > hi_score:
                    self.store.put('default',high_score=int(self.score))
        if self.score > self.hi_score:
            self.hi_score = self.score
            self.store.put(self.game_id,high_score=int(self.score))
        if platform == 'android' and self.players == 1:
            if self.score > 600:
                App.get_running_app().gs_achieve('achievement_score_of_600')
            if self.score > 800:
                App.get_running_app().gs_achieve('achievement_score_of_800')
            if self.score > 1000:
                App.get_running_app().gs_achieve('achievement_score_of_1000')
            if self.score > 1200:
                App.get_running_app().gs_achieve('achievement_score_of_1200')
                
class WordBar(BoxLayout):
    w_word_label = ObjectProperty()
    word = StringProperty()
    word_score = NumericProperty()
    can_pass = BooleanProperty()
    def __init__(self,**kwargs):
        super(WordBar,self).__init__(**kwargs)

class MessageBar(BoxLayout):
    message = StringProperty()
    def __init__(self,**kwargs):
        super(MessageBar,self).__init__(**kwargs)

    def active_player_changed(self, scorebar, active_player):
        if scorebar.players == 2:
            self.message = 'PLAYER %i\'S TURN'%scorebar.active_player

    def game_over(self, board, game_over):
        if game_over == True:
            if board.scorebar.players == 2:
                winner = 1 + (board.scorebar.score_2 > board.scorebar.score)
                if board.players[winner].type == 1:
                    self.message = 'PLAYER %i WINS'%winner
                else:
                    self.message = '%s WINS'%board.players[winner].name
            else:
                self.message = 'GAME OVER'
        else:
            self.message = ''
                
    def game_changed(self, scorebar, game_id):
        if scorebar.players == 2:
            return
        self.game_id = game_id
        if game_id != 'default':
            date = uspac.fromutc(datetime.datetime.utcnow())
            next_date = date + datetime.timedelta(days=1)
            next_date = next_date.replace(hour = 0, minute = 0, second = 0, microsecond = 0)
            delta = next_date - date
            if delta.days != 0:
                self.message = 'CHALLENGE DATE PROBLEM -- CHECK THE SYSTEM CLOCK'
            elif delta.seconds > 0:
                hours = delta.seconds // 3600
                minutes = delta.seconds // 60
                if hours > 0:
                    self.message = '%i HOUR%s LEFT'%(hours, 'S' if hours>1 else '')
                    Clock.schedule_once(lambda x: self.on_daily_challenge_timer(game_id), datetime.timedelta(hours=1).total_seconds())
                elif minutes > 0:
                    self.message = '%i MINUTE%s LEFT'%(minutes, 'S' if minutes>1 else '')
                    Clock.schedule_once(lambda x: self.on_daily_challenge_timer(game_id), datetime.timedelta(minutes=1).total_seconds())
                else:
                    self.message = '%i SECOND%s LEFT'%(delta.seconds, 'S' if delta.seconds>1 else '')
                    Clock.schedule_once(lambda x: self.on_daily_challenge_timer(game_id), datetime.timedelta(seconds=1).total_seconds())
            else:
                self.message = 'THE DAILY CHALLENGE HAS EXPIRED'
        else:
            self.message = ''

    def on_daily_challenge_timer(self, game_id):
        if game_id == self.game_id:
            self.game_changed(None, game_id)

class SlideWordsGameApp(App):
    colors = DictProperty()
    def build(self):
        try:
#            self.colors = colors.load_theme('default')
            self.colors = colors.load_theme(self.config.get('theme','theme'))
        except KeyError:
            self.colors = colors.load_theme('default')

        Builder.load_file('words.kv')
        self.gb = Board()
        Window.bind(on_keyboard = self.on_keyboard)

        if platform == 'android':
            self.use_google_play = self.config.getint('play', 'use_google_play')
            if self.use_google_play:
                googleplayclient.connect(self.activate_google_play_success, self.activate_google_play_failed, self.score_notification)
            else:
                Clock.schedule_once(self.ask_google_play, .5)

        return self.gb

    def set_next_theme(self):
        themes = list(colors.themes)
        ind = themes.index(self.config.get('theme','theme'))
        new_theme = themes[ind-1]
        self.config.set('theme', 'theme', new_theme)
        self.config.write()
        self.colors = colors.load_theme(themes[ind-1])
        self.gb.draw_background()

    def build_config(self, config):
        config.setdefaults('theme', {'theme': 'beach'})
        if platform == 'android':
            config.setdefaults('play', {'use_google_play': '0'})

    def open_settings(self, *args):
        pass

    def gs_score(self, score_type, score):
        if platform == 'android' and self.use_google_play>0 and score>0:
            googleplayclient.submit_score(score_type, int(score))

    def gs_get_score(self, name):
        if platform == 'android':
            if self.use_google_play>0:
                googleplayclient.get_score(name)
            else:
                self.ask_google_play()

    def gs_show_leaderboard(self, score_type):
        if platform == 'android':
            if self.use_google_play>0:
                googleplayclient.show_leaderboard(score_type)
            else:
                self.ask_google_play()

    def gs_achieve(self, achievement_id):
        if platform == 'android' and self.use_google_play>0:
            googleplayclient.unlock_achievement(achievement_id)

    def gs_inc_achieve(self, achievement_id):
        if platform == 'android' and self.use_google_play>0:
            googleplayclient.increment_achievement(achievement_id)

    def gs_show_achievements(self):
        if platform == 'android':
            if self.use_google_play>0:
                googleplayclient.show_achievements()
            else:
                self.ask_google_play()

    def ask_google_play(self, *args):
        popup = GooglePlayPopup()
        popup.open()

    def activate_google_play(self):
        self.config.set('play', 'use_google_play', '1')
        self.config.write()
        googleplayclient.connect(self.activate_google_play_success, self.activate_google_play_failed, self.score_notification)

    def activate_google_play_success(self, *args):
        self.use_google_play = 1

    def activate_google_play_failed(self, *args):
        self.use_google_play = 0

    def score_notification(self, score):
        self.gb.update_1000_games_tally(score)
        
    def on_keyboard(self, window, key, scancode=None, codepoint=None, modifier=None):
        '''
        used to manage the effect of the escape key
        '''
        if key == 27:
            if self.gb.score_detail_1p in self.gb.children:
                self.gb.remove_widget(self.gb.score_detail_1p)
            elif self.gb.score_detail_2p in self.gb.children:
                self.gb.remove_widget(self.gb.score_detail_2p)
            elif self.gb.instructions in self.gb.children:
                self.gb.remove_widget(self.gb.instructions)
            elif self.gb.multiplayer_menu in self.gb.children:
                self.gb.hide_multiplayer_menu()
            elif self.gb.leaderboard_menu in self.gb.children:
                self.gb.hide_leaderboard_menu()
            elif self.gb.menu not in self.gb.children:
                self.gb.show_menu()
            else:
                self.gb.hide_menu()
            return True
        return False

    def on_pause(self):
        '''
        trap on_pause to keep the app alive on android
        '''
        self.gb.save_state()
#        if platform == 'android':
#            googleplayclient.logout()
        return True

    def on_resume(self):
        pass
#        if platform == 'android':
#            googleplayclient.connect(self.activate_google_play_success, self.activate_google_play_failed, self.score_notification)

    def on_stop(self):
        self.gb.save_state()
        self.gb.active_player.abort()

if __name__ == '__main__':
    gameapp = SlideWordsGameApp()
    gameapp.run()

