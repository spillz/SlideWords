
default_theme = {
    'background': (0.7, 0.7, 0.9, 1),
    'tile': (0.5, 0.5, 0.75, 1),
    'tile_selected': (0, 0, 0.5, 1),
    'tile_letter_text': (0.9, 0.9, 0.9, 1),
    'word_score_background': (0, 0, 0.5, 1), #(0, 0, 0.8, 1),
    'word_score_text': (0.9, 0.9, 0.9, 1), #(0.9, 0.9, 0.9, 1),
    'score_text': (0.9, 0.9, 0.9, 1),
    'active_score_text': (0.5, 0.5, 0.75, 1),
    'checker': (0.8, 0.8, 0.9, 1),
    'move_candidates': (0.2, 0.3, 0.7, 1),
    'menu_button_background': (0.5, 0.8, 0.7, 1),
    }


beach_theme = {
    'background': (20,140,156,255),
    'tile': (255,241,156,255),
    'tile_selected': (232, 180, 120, 255),
    'tile_letter_text': (86, 148, 155, 255),
    'word_score_background' : (252, 200, 130, 255),
    'word_score_text': (86, 148, 155, 255),
    'score_text': (221, 238, 242, 255),
    'active_score_text': (254, 241, 156, 255),
    'checker': (0, 202, 199, 255),
    'move_candidates': (252, 200, 130, 255),
    'menu_button_background': (252, 136, 61, 255),
    }

themes = {
    'default': default_theme,
    'beach' : beach_theme
    }

def load_theme(theme_name):
    global background, tile, tile_selected, tile_letter_text, word_score_background, \
        word_score_text, score_text, active_score_text, checker, move_candidates, menu_button_background
    theme = themes[theme_name]
    if theme_name != 'default':
        c = lambda colors: tuple(1.0*col/255 for col in colors)
        theme = dict([(k, c(theme[k])) for k in theme])
    background = theme['background']
    tile = theme['tile']
    tile_selected = theme['tile_selected']
    tile_letter_text = theme['tile_letter_text']
    word_score_background = theme['word_score_background']
    word_score_text = theme['word_score_text']
    score_text = theme['score_text']
    active_score_text = theme['active_score_text']
    checker = theme['checker']
    move_candidates = theme['move_candidates']
    menu_button_background = theme['menu_button_background']
    return theme
