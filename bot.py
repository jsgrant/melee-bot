import melee
import random
import time
import inputs as Inputs

Buttons = melee.enums.Button
Actions = melee.enums.Action

class Bot:
    '''Framework for making controller inputs.
    Offline only implementation currently.'''

    def __init__(self, controller,
                 character=melee.Character.FOX,
                 stage=melee.Stage.FINAL_DESTINATION):
        self.controller = controller
        self.character = character
        self.stage = stage

    def act(self, gamestate):
        '''Main function called each frame of game loop with updated gamestate.'''

        if gamestate.menu_state in (melee.Menu.IN_GAME,
                                    melee.Menu.SUDDEN_DEATH):
            self.play_frame(gamestate)  # rand note, paused wont advance frame
        else:
            self.menu_nav(gamestate)

    def menu_nav(self, gamestate):
        '''Processes menus with given character, stage.'''
        melee.MenuHelper.menu_helper_simple(gamestate,
                                            self.controller,
                                            self.character,
                                            self.stage,
                                            '', # connect code
                                            0,  # cpu_level (0 for N/A)
                                            0,  # costume
                                            autostart=True)

    def play_frame(self, gamestate):
        '''Bot game logic implemented here.'''
        pass

# convenience/helpers/conditions that don't require self

def always(gamestate):
    return True

def never(gamestate):
    return False

class InputsBot(Bot):
    '''Adds inputs queue to main loop.

    Inputs should be always put into queue,
    never called directly/instantly with controller.
    First queued input will happen same frame of queueing.'''

    def __init__(self, controller, character, stage):
        super().__init__(controller, character, stage)
        self.queue = []

    def play_frame(self, gamestate):

        # a fix for leftover menu presses
        # if gamestate.frame < 0:
        #     self.queue = [(Inputs.release,)]
        #     return
        self.check_frame(gamestate)
        self.consume_next_inputs()

    def consume_next_inputs(self):
        '''Called each frame to press or release next buttons in queue.
        See inputs.py for expected inputs format.'''
        if self.queue:
            commands = self.queue.pop(0)
            for press, *button_args in commands:
                if len(button_args) > 1:
                    self.controller.tilt_analog(*button_args)
                else:
                    if press:
                        self.controller.press_button(*button_args)
                    else:
                        if button_args:
                            self.controller.release_button(*button_args)
                        else:
                            self.controller.release_all()

    def perform(self, input_sequence):
        '''Set queue to a sequence of inputs.
        Useful in lambdas where assignment is not allowed'''
        self.queue = list(input_sequence)  # need a (deep) copy of fragile variable

    def check_frame(self, gamestate):
        '''Decision making and input queueing happens here.'''
        pass

class CheckBot(InputsBot):
    '''Adds condition checker to main loop.

    Condition functions (self.when) take a gamestate parameter.
    Callbacks (self.do) take no parameters.
    Stops checking upon reaching condition.'''

    def __init__(self, controller,
                 character=melee.Character.FOX,
                 stage=melee.Stage.FINAL_DESTINATION):
        super().__init__(controller=controller,
                         character=character,
                         stage=stage)

        self.when = never
        self.do = lambda:None
        self.max_time = 30  # arbitrary init
        self.timer = self.max_time

    def check_frame(self, gamestate):
        '''Called each frame to check gamestate (and/or possibly self?) for condition,
        stopping check when True.'''
        if self.when(gamestate):
            self.when = never
            self.do()

    def times_up(self, gamestate):
        '''A condition check that ticks timer, returning True on expire.'''
        if self.timer > 0:
            self.timer -= 1
            return False
        else:
            self.timer = self.max_time
            return True

    def set_timer(self, n, do, repeat=True):
        '''Convenience function sets all required timer functions:
        n frames to wait, timer condition, callback.'''
        self.max_time = n
        self.timer = self.max_time
        if repeat:
            self.repeat(when=self.times_up,
                        do=do)
        else:
            self.when = self.times_up
            self.do = do

    def repeat(self, when, do):
        '''Keeps checking when condition (as opposed to the default stop checking).'''
        def do_and_wait_again():
            do()
            self.when = when
        self.when = when
        self.do = do_and_wait_again

    def finished_inputs(self, gamestate):
        '''A condition to loop inputs by returning True when queue is empty.'''
        return len(self.queue) == 0

# some gamestate conditions not needing self

def not_lasering(gamestate):
    # just for standing, no aerial actions
    return not gamestate.player[2].action in (Actions.LASER_GUN_PULL,
                                              Actions.NEUTRAL_B_CHARGING,
                                              Actions.NEUTRAL_B_ATTACKING)
def not_taunting(gamestate):
    return not gamestate.player[2].action in (Actions.TAUNT_LEFT,
                                              Actions.TAUNT_RIGHT)
def grounded(gamestate):
    return gamestate.player[2].on_ground

class FalcoBot(CheckBot):
    # working with previous features

    def __init__(self, controller):
        super().__init__(controller=controller,
                         character=melee.Character.FALCO,
                         stage=melee.Stage.FINAL_DESTINATION)

        # self.investigate_jumpframes()
        self.jumped = False
        self.set_shorthop_laser_strat()

    def set_standing_laser_strat(self):
        self.set_timer(2, lambda: self.perform(Inputs.laser()), repeat=True)
        # self.repeat(when=self.finished_inputs,
        #             do=lambda: self.perform(laser))

    def set_shorthop_laser_strat(self):
        self.jumped = False
        self.repeat(when=self.can_jump,
                    do=self.sh_laser)

    def set_jump_strat(self):
        self.jumped = False
        self.repeat(when=self.can_jump,
                    do=self.jump)

    def can_jump(self, gamestate):
        if grounded(gamestate):
            if self.jumped:
                return False
            else:
                return True
        else:
            self.jumped = False # safe to reset now
            return False

    def sh_laser(self):
        self.perform([*Inputs.wait(3), *Inputs.fastfall_laser_rand()])
        self.jumped = True

    def jump(self):
        self.perform([*Inputs.wait(3), *Inputs.shorthop()])
        self.jumped = True

    ### example of finding out frame data

    def investigate_jumpframes(self):
        self.prepause = 0
        self.jumped = False
        self.max_time = 45

        def timer_checking_jump(gamestate):
            if self.timer < 0:
                # print('timer up')
                title = 'prepause {} f,'.format(self.prepause)
                if self.jumped:
                    print(title, 'success')
                    # self.when = never
                    # return True
                else:
                    print(title, 'fail')
                # reset everything and inc pause frames
                self.timer = self.max_time
                self.prepause += 1
                self.jumped = False
                return True
            else:
                self.timer -= 1
                if not grounded(gamestate):
                    self.jumped = True  # should be success but just let timer tick
            return False

        self.repeat(when=timer_checking_jump,
                    do=self.jump_with_wait)

    def jump_with_wait(self):
        self.perform([*Inputs.wait(self.prepause), *Inputs.shorthop()])

    ### toxic demos, use responsibly

    def taunt(self):
        # interrupt activities to taunt asap.
        # keeps setting queue until taunting actually happens

        # self.last_when = self.when
        self.when = not_taunting
        self.do = lambda: self.perform([(Inputs.release,), *Inputs.taunt()])

    def ragequit(self): #, angry_misinput=True):
        # special pause case: frames not advanced in pause, so we have to
        # independently execute multiple presses outside of main loop.
        # generally poor use of inputs and lack of queue.
        inputs = [
            (True, Buttons.BUTTON_START),
            (True, Buttons.BUTTON_L),
            (True, Buttons.BUTTON_R),
            (True, Buttons.BUTTON_A),
        ]
        self.controller.release_all()
        for press, *button_args in inputs:
            self.controller.press_button(*button_args)
            time.sleep(0.01) # could be needed if incosistent timing?

class ControllableBot(InputsBot):
    # easier to control externally, eg from live thread or perhaps a twitch chat!

    def __init__(self, controller,
                 character=melee.Character.FALCO,
                 stage=melee.Stage.FINAL_DESTINATION):
        super().__init__(controller, character, stage)

        self.queue = []     # perhaps use a smarter/slightly more efficent type (like a real queue)?
        self.commands = self.init_commands()
        self.curr_sequence = []

    def init_commands(self):

        def wrapper(make):
            return lambda: self.set_curr_seq(make())

        return {cmd: wrapper(make) for cmd, make in {
            'laser': Inputs.laser,
            'sh': Inputs.shorthop,
            'shlaser': Inputs.jump_n_laser,  #fastfall_laser_rand
            'taunt': Inputs.taunt,
            'shield': Inputs.shield,
            'A': lambda: [(Inputs.A,), (Inputs.un_A,)],

        }.items()}

    def check_frame(self, gamestate):
        '''Called each frame to check gamestate (and/or possibly self?)
        and choose next actions.'''

        # test inputs
        if len(self.queue) == 0:
            self.perform(self.curr_sequence)
        # if self.timer == 0:
        #     self.queue = Inputs.laser

    def set_curr_seq(self, sequence):
        self.curr_sequence = [(Inputs.release,), *sequence]

class MultiCheckBot(InputsBot):

    FINISH_NOW = 1
    STOP_CHECKING = 2
    KEEP_CHECKING = 3

    def __init__(self, controller,
                 character=melee.Character.FALCO,
                 stage=melee.Stage.FINAL_DESTINATION):
        super().__init__(controller, character, stage)

        self.checks = {}

    def check_frame(self, gamestate):
        remove = []
        for condition, do in self.checks.items():
            if condition(self, gamestate):
                retval = do()
                if retval == MultiCheckBot.FINISH_NOW:
                    return
                elif retval == MultiCheckBot.STOP_CHECKING:
                    remove.append(condition)
        for condition in remove:
            del self.checks[condition]

    def something(self):
        pass
