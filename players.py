from globals import words, board_size
import threading
import random
import time
from kivy.clock import Clock


def weighted_choice(count, choices, seed):
    rstate = random.getstate()
    random.seed(seed)
    ch = choices.copy()
    output = set()
    for x in range(count):
        total = sum(w for c, w in ch.iteritems())
        r = random.randint(0, total-1)
        upto = 0
        for c, w in ch:
            if upto + w >= r:
                del ch[c]
                output.add(c)
                break
            upto += w
    random.setstate(rstate)
    return output


class Player(object):
    player_id = 1
    num_players = 2
    name = 'HUMAN'
    type = 1
    def __init__(self, board, pid):
        self.player_id = pid
        self.board = board

    def start_turn(self):
        pass

    def local_touch(self):
        return not self.board.game_over

    def abort(self):
        return True

    def reset(self):
        pass

        
class AITile:
    def __init__(self, tile):
        self.letter = str(tile.letter)
        self.value = int(tile.value)

class AIBoard(object):
    def __init__(self, tiles = None):
        if tiles == None:
            self._tiles = [[None]*board_size for t in range(board_size)]
        else:
            self._tiles = tiles

    def copy(self):
        return AIBoard([row[:] for row in self._tiles])

    def __getitem__(self, tup):
        return self._tiles[tup[0]][tup[1]]

    def __setitem__(self, tup, tile):
        self._tiles[tup[0]][tup[1]] = tile

    def __contains__(self, tup):
        if tup is None:
            return False
        return self._tiles[tup[0]][tup[1]]!=None

    def __delitem__(self, tup):
        self._tiles[tup[0]][tup[1]] = None

use_ai_board = False
        
class AIPlayer(Player):
    type = None
    vocab = 0 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = board_size #maximum length of words to check for 
    max_checks = 500000 #maximum number of word checks allowed before turn ends
    name = '' #no name suppresses from the list of playable AIs
    def __init__(self, board, pid):
        Player.__init__(self, board, pid)
        self._abort = False #set to true when a game is aborted
        self._dead = False #when a game is aborted, dead is set to true
        self.words = None
            
    def reset(self):
        self._dead = False

    def board_state(self):
        state = {} if not use_ai_board else AIBoard()
        for xy in self.board.tiles.iterkeys():
            state[xy] = AITile(self.board[xy])
        return state

    def empty_cells(self, state):
        empty_cells = []
        for x in range(board_size):
            for y in range(board_size):
                if (x,y) not in state:
                    empty_cells.append((x,y))
        return empty_cells

    def slideables(self, state, pos):
        slideables = []
#        if pos in state:
#            return []
        for dz in [(0,1), (0,-1), (1,0), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]:
            q = 1
            x,y = pos[0] + q*dz[0], pos[1] + q*dz[1]
            while 0<=x<board_size and 0<=y<board_size:
                if (x,y) in state:
                    if state[(x,y)] != 1: #if not an already selected tile, add it
                        slideables.append((x,y))
                    break
                q += 1
                x,y = pos[0] + q*dz[0], pos[1] + q*dz[1]
        return slideables

    def neighbors(self, state, pos):
        neighbors = []
        for diff in [(0,1), (0,-1), (1,0), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]:
            npos = pos[0]+diff[0], pos[1]+diff[1]
            if npos in state:
                neighbors.append(npos)

    def arrange_sel(self, state, sel):
        return [[s,s] if s in state else [None, s] for s in sel]

    def get_words_in_range(self, state, sel):
        sel = self.arrange_sel(state, sel)
        empty = [i for i in range(len(sel)) if sel[i][0] == None]
        if len(empty) == 0:
            return []
        state = state.copy()
        for s in sel:
            if s[0] in state:
                state[s[0]] = 1
        candidates = []
        def get_words_recurs(state, k):
            dst = sel[empty[k]][1]
            state[dst] = 1
            for ss in self.slideables(state, dst):
                if self._abort:
                    return []
                if self.counter>self.max_checks:
                    return
                tmp = state[ss]
                del state[ss]
                sel[empty[k]][0] = ss
                if k < len(empty) - 1:
                    get_words_recurs(state, k+1)
                else:
                    self.counter += 1
                    word = ''.join([self.init_state[s[0]].letter for s in sel])
                    if word in self.words or word[::-1] in self.words:
                        score = sum([self.init_state[s[0]].value for s in sel])*len(word)
                        nsel = [[s[0],s[1]] for s in sel]
                        candidates.append([word, score, nsel])
                state[ss] = tmp
            del state[dst]
        get_words_recurs(state, 0)
        return candidates

    def coord_list(self, d, position):
        if d == (1, 0):
            return [(x, position) for x in range(board_size)]
        if d == (0, 1):
            return [(position, y) for y in range(board_size)]
        if d == (1, 1):
            if position >= 0:
                return [(xy + position, xy) for xy in range(board_size - position)]
            else:
                return [(xy, xy - position) for xy in range(board_size + position)]
        if d == (1, -1):
            if position >= 0:
                return [(xy + position, board_size - 1 - xy) for xy in range(board_size - position)]
            else:
                return [(xy, board_size -1 - xy + position) for xy in range(board_size + position)]


    def words_on_line(self, state, d, position):
        '''
        iterates over the letters on a line in `state` given by the integer `position` in the
        range -(board_size - 1) to +(board_size -1), and direction `d` a tuple indicating
        the direction (1,0), (0,1) (1,1) or (-1,1) of search.
        Returns a list of candidates, where each candidate is a list containing
            the word
            the score
            the selection of tiles (a tuple containing src and dest of each tile in the word)
        '''
        candidates = []
        coords = self.coord_list(d, position)
        for start_point in range(len(coords)):
            for end_point in range(start_point + 1, min(len(coords), start_point+self.max_word_len)):
                print 'AI step',self.counter
                if self._abort:
                    return []
                if self.counter>self.max_checks:
                    return candidates
                candidates += self.get_words_in_range(state, coords[start_point:end_point+1])
        return candidates

    def find_move(self):
        #TODO: Needs to be on the thread (could set it up the first time the player has a turn)
        if self.words == None:
            if self.vocab <= 0:
                self.vocab = len(words)
                self.words = words
            elif self.random_vocab:
                self.words = weighted_choice(self.vocab, words, self.random_vocab_seed)
            else:
                import operator
                self.words = dict(sorted(words.items(), key=operator.itemgetter(1))[-self.vocab:])

        self.counter = 0
        state = self.init_state.copy()
        candidates = []
        empty = self.empty_cells(state)
        lines = set()
        for e in empty:
            lines.add((1,0,e[1]))
            lines.add((0,1,e[0]))
            lines.add((1,1,e[1]-e[0]))
            lines.add((1,-1,e[0]-e[1]))
        for l in lines:
            candidates += self.words_on_line(state, l[:2], l[2])
            if self.counter>self.max_checks:
                break
            if self._abort:
                self._abort = False
                return
        if len(candidates)>0:
            max_score = max([c[1] for c in candidates])
            best_candidates = [c for c in candidates if c[1] == max_score]
            for b in best_candidates:
                print b
            print 'number candidates',len(best_candidates)
            Clock.schedule_once(lambda *args: self.found_word(random.choice(best_candidates)),0.001)
            return
        Clock.schedule_once(lambda *args: self.no_word_found(),0.001)

    def start_turn(self):
        self.init_state = self.board_state()
        self.thread = threading.Thread(target = self.find_move)
        self.thread.start()

    def found_word(self, choice):
        word, score, self.sel = choice
        self.do_next()

    def no_word_found(self):
        self.sel = []
        self.do_next()

    def do_next(self):
        try:
            if self._dead:
                return
            src, dest = self.sel.pop(0)
            self.board.select(self.board[src], dest)
            Clock.schedule_once(lambda *args: self.do_next(), 0.5)
        except:
            Clock.schedule_once(lambda *args: self.end_turn(), 2.0)

    def end_turn(self):
        if self._dead:
            return
        self.board.end_turn()

    def local_touch(self):
        return False

    def abort(self):
        if self.thread.is_alive():
            self._abort = True
            while self._abort == True:
                time.sleep(0.01)
        self._dead = True
        return True
                
class Antrax(AIPlayer):
    name = 'AI ANTRAX'
    type = 2
    vocab = 5000 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = 5 #maximum length of words to check for 
    max_checks = 100000 #maximum number of word checks allowed before turn ends
    def __init__(self, board, pid):
        AIPlayer.__init__(self, board, pid)
                
class Blaine(AIPlayer):
    name = 'AI BLAINE'
    type = 3
    vocab = 7000 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = 7 #maximum length of words to check for 
    max_checks = 200000 #maximum number of word checks allowed before turn ends
    def __init__(self, board, pid):
        AIPlayer.__init__(self, board, pid)

class Cyclops(AIPlayer):
    name = 'AI CYCLOPS'
    type = 4
    vocab = 15000 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = 7 #maximum length of words to check for 
    max_checks = 200000 #maximum number of word checks allowed before turn ends
    def __init__(self, board, pid):
        AIPlayer.__init__(self, board, pid)

class Doctor(AIPlayer):
    name = 'AI DOCTOR'
    type = 5
    vocab = 15000 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = board_size #maximum length of words to check for 
    max_checks = 200000 #maximum number of word checks allowed before turn ends
    def __init__(self, board, pid):
        AIPlayer.__init__(self, board, pid)

class Earth(AIPlayer):
    name = 'AI EARTH'
    type = 6
    vocab = 20000 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = board_size #maximum length of words to check for 
    max_checks = 200000 #maximum number of word checks allowed before turn ends
    def __init__(self, board, pid):
        AIPlayer.__init__(self, board, pid)

class Fess(AIPlayer):
    name = 'AI FESS'
    type = 7
    vocab = 25000 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = board_size #maximum length of words to check for 
    max_checks = 300000 #maximum number of word checks allowed before turn ends
    def __init__(self, board, pid):
        AIPlayer.__init__(self, board, pid)

class Golem(AIPlayer):
    name = 'AI GOLEM XIV'
    type = 8
    vocab = 50000 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = board_size #maximum length of words to check for 
    max_checks = 500000 #maximum number of word checks allowed before turn ends
    def __init__(self, board, pid):
        AIPlayer.__init__(self, board, pid)

class Harlie(AIPlayer):
    name = 'AI HARLIE'
    type = 9
    vocab = 0 #number of words in vocabulary (0 for all)
    random_vocab = False #True to randomly determine the vocab (weighted by frequency)
    random_vocab_seed = 0 #The seed to use to draw the vocab
    max_word_len = board_size #maximum length of words to check for 
    max_checks = 500000 #maximum number of word checks allowed before turn ends
    def __init__(self, board, pid):
        AIPlayer.__init__(self, board, pid)
                
def get_all_subclasses(cls):
    all_subclasses = []

    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))

    return all_subclasses

player_types = dict([(cls.type, cls) for cls in [Player] + get_all_subclasses(Player) if cls.name != ''])

if __name__ == '__main__':
    print player_types
    print AIPlayer.type, Player.type
