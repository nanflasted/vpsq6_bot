from twitchio.ext import commands
from twitchio.ext import routines
import os
import pickle
import random
import numpy as np
import copy
import asyncio
import itertools
from hashlib import sha256

DEFAULT_BALANCE = 10000
ACCESS_TOKEN = "4nvlaqguf8fsc6bvz3wqi3jbk8ocd5"
DEFAULT_SAVE_LOCATION = "./accounts.pkl"
ALLIES = ["vidya_vinny", "diego_sparx"]
ENEMIES = ["ginobili", "forever21"]
MODS = ["vpsqofficial", "nanflasted"]
HOUSE_NAME = "barelynoers"


def check_is_mod(ctx: commands.Context) -> bool:
    return bool(ctx.author.name in MODS)


class UserBank:

    name = ""
    balance: int = 0
    has_cocktail: bool = False

    def check_balance(self) -> int:
        return self.balance

    def add_money(self, amt: int) -> None:
        self.balance += amt 
        if self.balance < 0:
            self.balance = 0
    
    def set_balance(self, amt: int) -> None:
        self.balance = amt

    def __init__(self, name: str, balance: int | None = None):
        self.name = name
        self.set_balance(balance or DEFAULT_BALANCE)
        self.has_cocktail = False
    
    def give_cocktail(self):
        self.has_cocktail = True

    def clear_cocktail(self):
        self.has_cocktail = False


# works!
class BookKeeper(commands.Cog):
    """
    Cog to manage the accounts and keep the book.

    Most of the actual operations are made to be staticmethods because
    other cogs (like SpecialEvents) might need them too.

    It makes sense that the Bot will actually "own" the book object,
    instead of having the cog own it.
    """

    # map between user name and their bank account
    # make sure we give vinny, diegosparx, ginobili and forever21 some amount of money initially
    default_book: dict[str, UserBank] = {
        "vidya_vinny": UserBank("vidya_vinny", 10000),
        "diego_sparx": UserBank("diego_sparx", 20000),
        "ginobili": UserBank("ginobili", 500000),
        "forever21": UserBank("forever21", 500000),
        # the house/bank, who has practically infinite money
        HOUSE_NAME: UserBank(HOUSE_NAME, 1e20),
    }

    #################################### Managerial operations ###############################

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(self.bot, "book") or not self.bot.book:
            if os.path.exists(DEFAULT_SAVE_LOCATION):
                with open(DEFAULT_SAVE_LOCATION, "rb") as f:
                    self.bot.book = pickle.load(f)
            else:
                self.bot.book = copy.deepcopy(self.default_book)
        self.save_book.start()
                
    @routines.routine(minutes=5)
    async def save_book(self) -> None:
        with open(DEFAULT_SAVE_LOCATION, "wb+") as f:
            pickle.dump(self.bot.book, f)

    @commands.command(name="save_book")
    async def save_book_command(self, ctx: commands.Context):
        if not check_is_mod(ctx):
            await ctx.send("The Book Keeper continues on his business, uninterested in your request...")
            return

        with open(DEFAULT_SAVE_LOCATION, "wb+") as f:
            pickle.dump(self.bot.book, f)
        await ctx.send("The Book Keeper writes down the recent transactions...")
    
    #################################### Chips operations ###############################

    @staticmethod
    def open_account_op(book: dict[str, UserBank], name: str) -> str:
        """
        when users try to interact for the first time, open up an account for them
        and give then a default number of chips.
        """
        if name in book:
            return (
                "The cashier clerk frowns, "
                f"\'{name} already gots an account, type !balance to check your balance!\'"
            )
        else:
            book[name] = UserBank(name, DEFAULT_BALANCE)
            return (
                f"The cashier clerk smiles, \n"
                f"\'An account with {DEFAULT_BALANCE} chips has been opened for you, {name}! "
                f"Welcome to BarelyNoer's, enjoy your stay!\'"
            )

    @commands.command(name="buyin", aliases=["buy-in", "buy_in"])
    async def open_account_command(self, ctx: commands.Context):
        name = ctx.author.name
        result = BookKeeper.open_account_op(self.bot.book, name)
        await ctx.send(result)

    @staticmethod
    def transfer_op(book: dict[str, UserBank], source: str, target: str, amount: int) -> str:
        if source not in book:
            return (
                f'{source} tried to donate chips, but does not yet have '
                f'an account. type !buyin to open an account!'
            )
        if amount == 0:
            return f'{source} tried to donate nothing. But why?'
        if amount < 0:
            return f'{source} tried to steal from {target}! For shame!'
        if target not in book:
            return (
                f"Hmm... {source} tried to give some chips to {target}, only to find that "
                "name coming up empty..."
            )
        if target in ENEMIES and source not in ALLIES:
            return (
                f'{source} tried to be a traitor against the cause..., but '
                f'the Neo-Vegas security found the transaction to be fraudulent '
                f'and stopped the transaction...'
            )
        
        source_current = BookKeeper.check_op(book, source, True)
        if amount > source_current:
            return (
                f'{source} tried to donate chips to {target}, but is a bit too poor...'
                f'at the moment. Perhaps {source} will try their hands in a game next, '
                f'or wait around for some cocktails?'
            )
        
        book[source].add_money(-amount)       
        book[target].add_money(amount)
        return f'{source} has generously gifted {target} {amount} chips!! How nice!'

    @commands.command(name="donate", aliases=["gift"])
    async def donate_command(self, ctx: commands.Context, amount: int | float, target: str):
        """
        gift some money to one of the allies, or someone else
        """
        amount = int(amount)
        try:
            result = BookKeeper.transfer_op(self.bot.book, ctx.author.name, target, amount)
            await ctx.send(result)
        except commands.ArgumentParsingFailed:
            await ctx.send("failed to send chips! try !donate [amount] [receipient]")

    @staticmethod
    def check_op(book: dict[str, UserBank], source: str, number_only: bool = False) -> str:
        if source not in book:
            return (
                f'We tried to check chips balance, but {source} does not yet have '
                f'an account. type !buyin to open an account!'
            ) if not number_only else 0
        return (
            f'{source} currently has {book[source].check_balance()} chips!'
        ) if not number_only else book[source].check_balance()

    @commands.command(name="balance", aliases=["check"])
    async def check_command(self, ctx: commands.Context, target: str | None):
        """
        check the amount of chips someone has
        """
        to_check = target or ctx.author.name
        await ctx.send(BookKeeper.check_op(self.bot.book, to_check))

    @commands.command(name="bonus")
    async def bonus_command(self, ctx: commands.Context, amount:int, target: str):
        """
        gift target some money on the house.
        """
        if check_is_mod(ctx):
            await ctx.send(BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, target, amount))
        else:
            await ctx.send("Nice try! But you are not allowed to steal from the bank...")


    #################################### Cocktail operations ###############################
    @staticmethod
    def clear_cocktails_op(book: dict[str, UserBank]) -> None:
        """
        clear the state of cocktails for all players in preparation for 
        new cocktail round
        """
        for user, bank in book.items():
            bank.clear_cocktail()

    @staticmethod
    def check_cocktails_op(book: dict[str, UserBank], target: str) -> bool:
        return book[target].has_cocktail

    @staticmethod
    def give_cocktails_op(book: dict[str, UserBank], target: str) -> None:
        book[target].give_cocktail()
        

# works!
class SpecialEvents(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.cocktail_lady_present_flag = False
        self.bot.cocktail_round_count = 0
        self.special_bets.start()
        self.cocktail_lady.start()

    # start the very first special event a bit later
    @routines.routine(minutes=2, wait_first=True)
    async def special_bets(self) -> None: # works
        """
        Sometimes vinny/diego will initiate a bet against ginobili/forever21,
        resulting in a random chip gain/loss.

        We will put this random bet here because no games are actually played and
        we only need to change the bank account directly and send a message.

        Because vinny/diego start with a smaller account, we need to rig the bet
        in their favour a bit, because otherwise they WILL lose all their moneys
        somewhat quickly.

        Extremely overengineered event...
        """
        ally_bettor = random.choice(ALLIES)
        enemy_bettor = random.choice(ENEMIES)

        # can't bet more than what they have
        max_bet_amount = min(
            BookKeeper.check_op(self.bot.book, ally_bettor, True),
            BookKeeper.check_op(self.bot.book, enemy_bettor, True),
        )
        # segment the possible bets into 20 buckets given the massive range
        bet_buckets = np.linspace(50, max_bet_amount, 21).astype(int)
        # this random distribution here makes sure that we don't just randomly
        # max bet... because vinny and diego are reasonable people, not menaces.
        bet_bucket = np.random.geometric(0.15)
        if bet_bucket > 20:
            bet_bucket = 20
        bet_amount = np.random.randint(bet_buckets[bet_bucket - 1], bet_buckets[bet_bucket])

        # extremely overengineered rigged bets
        # make it such that allies are somewhat more likely to win 
        # esp. the bigger the bet gets
        # this number is not the odds technically, just a result
        odds = np.tanh(np.random.normal(bet_bucket / 20.))
        # avoid draws (wtf?)
        if odds == 0:
            odds = 0.0000001
        ally_won = odds > 0

        if ally_won:
            BookKeeper.transfer_op(self.bot.book, enemy_bettor, ally_bettor, bet_amount)
        else:
            BookKeeper.transfer_op(self.bot.book, ally_bettor, enemy_bettor, bet_amount)

        adjs = ["overwhelming", "feeble", "incredible", "sheer", "questionable", "sketchy"]
        opener = ["Rumour has it", "Extra, Extra!!", "Heard over the grapevines", "Is it true?"]
        message = (
            f"{random.choice(opener)}... {ally_bettor} just made a bet against {enemy_bettor}, "
            f"and with the {random.choice(adjs)} {np.abs(odds):.5%} of luck, {ally_bettor} "
            f"{'won' if ally_won else 'lost'} {bet_amount} chips!"
        )
        await self.bot.connected_channels[0].send(message)

        # determine when to initiate the next bet
        # random number of minutes with a longer tail, an EV of 5.25 mins
        # median of ~4.7 mins and clipped off at 11 mins max
        next_bet_mins = int(np.ceil(np.random.gamma(3.5, 1.5)))
        if next_bet_mins > 11:
            next_bet_mins = 11
        self.special_bets.change_interval(minutes=next_bet_mins)

    @routines.routine(minutes=5, wait_first=True)
    async def cocktail_lady(self) -> None: # works
        """
        Sometimes the cocktails lady comes around and offers a drink...
        and some chips for free, because BarelyNoer's is just nice like
        that.

        But she does not stay around forever... in fact only for a minute
        
        To do this, we set a flag on for cocktail lady related commands, 
        asyncio sleep for the duration, then shut off the flag. We then
        block the commands to the cocktail lady if she isn't around.
        """
        self.bot.cocktail_lady_present_flag = True
        self.bot.cocktail_round_count += 1
        BookKeeper.clear_cocktails_op(self.bot.book)
        cocktail_lady_message = random.choice(['"Playing alone, handsome?"', '"Cocktails...? Cocktails??"', '"Want something to drink today?"', '"What can I getcha?"'])
        await self.bot.connected_channels[0].send(
            "A faint voice echoes throughout the air,"
            f"{cocktail_lady_message} "
            'Yes, She is here -- the fabled cocktail lady -- if only for a couple of minutes. type !cocktail [cocktail] '
            'to get a cocktail ... with some guac and Chips, on the house!'
        )
        await self.bot.connected_channels[0].send(
            "Legend says the number of chips you get with each cocktail changes every other time the cocktail lady comes around..."
        )
        await asyncio.sleep(120)
        self.bot.cocktail_lady_present_flag = False

        # determine how long until the cocktail lady's next visit
        # random number of minutes with a longer tail, an EV of 11 mins
        # median of ~18 mins and clipped off at 20 mins max
        next_visit_mins = int(np.ceil(np.random.gamma(5.5, 2)))
        if next_visit_mins > 20:
            next_visit_mins = 20
        self.cocktail_lady.change_interval(minutes=next_visit_mins)
        await self.bot.connected_channels[0].send(
            "Just like that, the cocktail lady's gone. But before she left, she slipped "
            f"you a note... 'don\'t you worry, I\'ll be back in {next_visit_mins} minutes'"
        )

    @commands.command(name="cocktail")
    async def cocktail_command(self, ctx: commands.Context, *, cocktail: str):
        """
        players can get some cocktails when the cocktail lady comes around,
        we make it such that people can input some arbitrary string and get some numbers back
        and such that it's consistent across 2 rounds, so people can exploit it a bit 
        """
        player = ctx.author.name
        if not self.bot.cocktail_lady_present_flag:
            await ctx.send("The cocktail lady is currently not around -- how about some patience?")
            return
        if BookKeeper.check_cocktails_op(self.bot.book, player):
            await ctx.send(f'"Sorry {player}," said the cocktail lady, "only one cocktail per round at a time..."')
            return

        # make sure we salt the cocktail so that the chips count for each cocktail changes every 2 rounds
        salt = str(np.ceil(self.bot.cocktail_round_count / 2))
        cocktail_secret = sha256((salt+cocktail+salt).encode()).hexdigest()
        # get first 5 non-zero digits in the sha256
        # if somehow there are no digits... give 1 chip...
        chip_digits = [int(c) for c in cocktail_secret if c.isnumeric() and c!='0'][:5] or [1.0025]
        # yes you get no chips if you somehow draw 5 ones.
        # draw log_1.0025^(PROD(digits)) chips, this way it still monotonically goes up, but doesn't go to an insane amount
        # max you can draw is about 4400 chips, which is a lot, but you have to get kinda lucky.
        # on average people probably will draw ~2.5k to 3k chips
        chip_gain = int(np.ceil(np.log(np.product(chip_digits)) / np.log(1.0025)))
        BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, player, chip_gain)
        BookKeeper.give_cocktails_op(self.bot.book, player)
        await ctx.send(f"{ctx.author.name} asked for a drink of {cocktail}, and got a free side of guac with {chip_gain} chips, very cool")


class Dealer(commands.Cog):
    """
    Dealer of games!
    """
    ROULETTE_PAYOUTS = {}
    ROULETTE_WINCONS = {}

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.game_registry = {"roulette": {}, "blackjack_decks": {}, "blackjack_hands": {}}
        self.init_roulette_rules()
        self.bot.roulette_spinning = False
        self.init_blackjack_rules()

    #################################### Roulette stuff #####################################
    # works!!!

    def init_roulette_rules(self):
        # payouts
        for bet in ["red", "black", "odd", "even", "small", "big"]:
            self.ROULETTE_PAYOUTS[bet] = 1
        for bet in range(37):
            self.ROULETTE_PAYOUTS[bet] = 36
        for bet in ["column1", "column2", "column3", "dozen1", "dozen2", "dozen3"]:
            self.ROULETTE_PAYOUTS[bet] = 2
        self.ROULETTE_PAYOUTS["00"] = 36
        self.ROULETTE_PAYOUTS["green"] = 18
        for k,v in self.ROULETTE_PAYOUTS.items():
            # plus 1 because we took the initial bet from the player
            self.ROULETTE_PAYOUTS[k] = v+1

        # wincons
        red_array = np.array([
            1, 3, 5, 7, 9,
            12, 14, 16, 18,
            19, 21, 23, 25, 27,
            30, 32, 34, 36
        ])
        self.ROULETTE_WINCONS["red"] = red_array
        self.ROULETTE_WINCONS["black"] = np.array(
            [i for i in np.arange(1,37) if i not in red_array]
        )
        # cheat a bit and use -1 for 00
        self.ROULETTE_WINCONS["green"] = np.array([0, -1])
        odd = np.arange(1, 37, 2)
        self.ROULETTE_WINCONS["odd"] = odd
        self.ROULETTE_WINCONS["even"] = odd + 1
        small = np.arange(1,19)
        self.ROULETTE_WINCONS["small"] = small
        self.ROULETTE_WINCONS["big"] = small + 18
        columns = np.arange(1, 37, 3)
        self.ROULETTE_WINCONS["column1"] = columns
        self.ROULETTE_WINCONS["column2"] = columns + 1
        self.ROULETTE_WINCONS["column3"] = columns + 2
        dozens = np.arange(1,13)
        self.ROULETTE_WINCONS["dozen1"] = dozens
        self.ROULETTE_WINCONS["dozen2"] = dozens + 12
        self.ROULETTE_WINCONS["dozen3"] = dozens + 24
        for i in range(37):
            self.ROULETTE_WINCONS[i] = [i]
        self.ROULETTE_WINCONS["00"] = [-1]

        # make them all sets for the fast
        for bet, cond in self.ROULETTE_WINCONS.items():
            self.ROULETTE_WINCONS[bet] = set(cond)

    async def roulette_clearing(self, roulette_registry: dict, result: int):
        """
        pay the players (or the bank) and clear the table of chips
        """
        for player, (bet, amount) in roulette_registry.items():
            player_won = result in self.ROULETTE_WINCONS[bet]
            if player_won:
                payout = self.ROULETTE_PAYOUTS[bet] * amount
                BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, player, payout)
                await self.bot.connected_channels[0].send(f"{player} hit the {bet} bet and got {payout} chips!")
            else:
                await self.bot.connected_channels[0].send(f"Unfortunately the {bet} bet did not hit for {player}, {amount} chips were lost...")
        # clean up the table
        self.bot.game_registry["roulette"] = {}

    async def roulette_spin(self):
        """
        handle the "spinning" of the roulette wheel
        """
        self.bot.roulette_spinning = True
        await self.bot.connected_channels[0].send("The roulette wheel spins and spins, the pill unraveling the threads of fate...")
        await self.bot.connected_channels[0].send("And it shall continue to spin... for 90 seconds...")
        await asyncio.sleep(30)
        await self.bot.connected_channels[0].send("10 seconds until the roulette wheel stops...")
        await asyncio.sleep(7)
        for i in range(3, 0, -1):
            await self.bot.connected_channels[0].send(f"{str(i)}...")
            await asyncio.sleep(1)
        result = np.random.randint(-1, 37)
        await self.bot.connected_channels[0].send(f"The dizzying revolutions come to a halt and the marble falls to the slot! The number is ... {str(result) if result>=0 else '00'}!")
        await self.roulette_clearing(self.bot.game_registry["roulette"], result)
        self.bot.roulette_spinning = False

    @commands.command(name="roulette")
    async def roulette_command(self, ctx: commands.Context, amount: int, bet: int | str):
        player = ctx.author.name
        if isinstance(bet, str):
            bet = bet.lower()
        if (amount <= 0) or (amount>BookKeeper.check_op(self.bot.book, player, True)):
            await ctx.send(
                f'The dealer stares at {player} blankly and says, '
                '"how about just enjoying some cocktails for now if you don\'t got them chips?"'
            )
            return
        if (bet not in self.ROULETTE_WINCONS):
            await ctx.send(
                f'The dealer return the chips to {player}, '
                '"I\'m afraid this is not a valid bet..., here are '
                f'all the options you can bet on: {", ".join([str(bet) for bet in self.ROULETTE_WINCONS.keys()])}.'
            )
            return
        if player in self.bot.game_registry["roulette"]:
            await ctx.send(
                f'The dealer stops the {player}, '
                '"looks like you already have a bet this time around -- please wait for the results..."'
            )
            return
        
        self.bot.game_registry["roulette"][player] = (bet, amount)
        BookKeeper.transfer_op(self.bot.book, player, HOUSE_NAME, amount)
        if not self.bot.roulette_spinning:
            await ctx.send(
                f'{player} approaches the roulette table and places a {amount} chips bet on {bet}...'
                'the Dealer motions to spin the wheel...'
            )
            asyncio.create_task(self.roulette_spin())
            # register the bet
        else:
            await ctx.send(
                f'{player} joins the ongoing roulette game, and places a {amount} chips bet on {bet}...'
            )

    #################################### Blackjack stuff #####################################
    # Works!!!

    def init_blackjack_rules(self):
        """
        3 deck blackjack... because why not?
        """
        self.BLACKJACK_DECK = list(itertools.product('CDHS',range(1,14))) * 3
        self.BLACKJACK_BET_RANGE = [100, 2000]
        self.BLACKJACK_VALUES = {}
        for i in range(1, 11):
            self.BLACKJACK_VALUES[i] = i
        for i in range(11, 14):
            self.BLACKJACK_VALUES[i] = 10
        self.BLACKJACK_REPR = {}
        for i in range(2,11):
            self.BLACKJACK_REPR[i] = str(i)
        self.BLACKJACK_REPR[1] = "A"
        self.BLACKJACK_REPR[11] = "J"
        self.BLACKJACK_REPR[12] = "Q"
        self.BLACKJACK_REPR[13] = "K"
        self.BLACKJACK_REPR["C"] = "♣"
        self.BLACKJACK_REPR["D"] = "♢"
        self.BLACKJACK_REPR["H"] = "♡"
        self.BLACKJACK_REPR["S"] = "♠"

    def check_value(self, hand: list[tuple[str, int]]) -> list[int]:
        values_map = [self.BLACKJACK_VALUES[card[1]] for card in hand]
        num_aces = len([card[1] for card in hand if card[1]==1])
        result = [sum(values_map)]
        for i in range(0, num_aces):
            result.append(result[i]+10)
        alive_results = sorted([r for r in result if r<=21])
        bust_results = sorted([r for r in result if r>21])
        if alive_results:
            return alive_results
        else:
            return bust_results[:1]

    def repr_card(self, card: tuple[str, int]) -> str:
        return self.BLACKJACK_REPR[card[0]] + self.BLACKJACK_REPR[card[1]]

    def repr_hand(self, hand: list[tuple[str, int]]) -> str:
        return ", ".join([self.repr_card(card) for card in hand])

    def shuffle_op(self, player: str):
        new_deck = (copy.deepcopy(self.BLACKJACK_DECK))
        np.random.shuffle(new_deck)
        self.bot.game_registry["blackjack_decks"][player] = new_deck
        return (
            'The dealer shuffles up the deck ... '
            f'"Here, {player}, the decks are ready just for you.'
        )

    async def new_hand_op(self, ctx:commands.Context, amount: int, player: str):
        if self.bot.game_registry["blackjack_hands"].get(player) is not None:
            await ctx.send(
                f'The dealer stops the {player}, '
                '"looks like you already have a hand on going -- please finish playing your hand..."'
            )
            return
        
        players_deck = self.bot.game_registry["blackjack_decks"][player]
        # before we deal new hands, shuffle if we have less than or equal to 26 cards
        if len(players_deck) <= 13:
            await ctx.send(self.shuffle_op(player))

        player_hand = [players_deck.pop(), players_deck.pop()]
        await ctx.send(f"The Dealer hands {player} {self.repr_hand(player_hand)}...")
        dealer_hand = [players_deck.pop(), players_deck.pop()]
        await ctx.send(f"and shows a {self.repr_card(dealer_hand[0])} for himself...")
        
        # handle naturals
        # because no matter what, if we hit a blackjack the hand is over
        # and there's no continuation to the next step.. we would need to go back to 
        # the beginning state next time
        if self.check_value(player_hand)[-1] == 21:
            await ctx.send(f"{player} does a double take -- it's {self.repr_hand(player_hand)}, a blackjack!")
            if self.check_value(dealer_hand)[-1] == 21:
                BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, player, amount) 
                await ctx.send(f"The Dealer flips his hidden card with a smug grin -- {self.repr_hand(dealer_hand)} ... it's a push...")
            else:
                await ctx.send(f"The Dealer does not have a blackjack -- having {self.repr_hand(dealer_hand)}... {player} wins a natural!")
                if self.bot.cocktail_lady_present_flag:
                    await ctx.send(f'"Amazing! The cocktail lady is currently around... you win our promotional payout of 8x your bet, {8*amount}!!"')
                    # 9x here because we took the money away from the player earlier
                    BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, player, 9*amount)
                else:
                    await ctx.send(f'"Congratulations! You win the natural blackjack payout of 2x your bet, {2*amount}!"')
                    BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, player, 3*amount)
            return

        # if no naturals, register the hand for next steps
        self.bot.game_registry["blackjack_hands"][player] = (player_hand, dealer_hand, amount)

    def hit_op(self, player: str, actor: str) -> list[tuple[str, int]]:
        """
        pop a card outta the deck and hit the hand with it
        then return the card that was put into the hand (so that upstream
        can send message)
        """
        player_hand, dealer_hand, amt = self.bot.game_registry["blackjack_hands"][player]
        deck = self.bot.game_registry["blackjack_decks"][player]
        card = deck.pop()
        if actor == "player":
            player_hand.append(card)
        else:
            dealer_hand.append(card)
        self.bot.game_registry["blackjack_hands"][player] = (player_hand, dealer_hand, amt)

        return player_hand if actor=="player" else dealer_hand

    async def player_hit(self, ctx: commands.Context):
        player = ctx.author.name
        hand = self.hit_op(player, actor="player")
        await ctx.send(
            f"The Dealer pulls a {self.repr_card(hand[-1])} out of the shoe and tosses it to {player}, "
            f"making the hand {self.repr_hand(hand)}."
        )
        values = self.check_value(hand)
        if values[0] > 21:
            # handle busting
            amt = self.bot.game_registry["blackjack_hands"][player][2]
            await ctx.send(f"Unfortunately, that means {player} bust, losing {amt} chips in the process... better luck next hand!")  
            # clear the registries
            self.bot.game_registry["blackjack_hands"][player] = None
        return

    @commands.command(name="hit")
    async def hit_command(self, ctx: commands.Context):
        player = ctx.author.name
        if not self.bot.game_registry["blackjack_hands"].get(player):
            await ctx.send(
                '"Can\'t hit if ya ain\'t got a hand, '
                f'{player}." Try !blackjack to start a new hand!'
            )
            return

        await self.player_hit(ctx)

    async def player_stand(self, ctx:commands.Context):
        """
        if player stands, this state machine ends (loops?) and we should go back 
        to new hand after this
        """
        player = ctx.author.name
        player_hand, dealer_hand, amount = self.bot.game_registry["blackjack_hands"][player]
        # we can assume player stands on the highest value here if Ace
        # so we can safely use -1 here
        player_value = self.check_value(player_hand)[-1]
        await ctx.send(f"{player} stands on {player_value}...")
        # dealer always has hard aces
        await ctx.send(
            f"The Dealer reveals his hidden card {self.repr_card(dealer_hand[1])}, "
            f"making his hand worth {self.check_value(dealer_hand)[-1]}"
        )
        while self.check_value(dealer_hand)[-1]<17:
            dealer_hand = self.hit_op(player, actor="dealer")
            await ctx.send(f"The dealer hits, gets a {self.repr_card(dealer_hand[-1])}")
        
        dealer_value = self.check_value(dealer_hand)[-1]
        if dealer_value > 21:
            # handle dealer bust
            BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, player, amount*2) # 2x because we took the original bet
            await ctx.send(f"The Dealer gets {dealer_value} and busts, {player} wins {amount} chips!")
        else:
            await ctx.send(f"The Dealer stands on {dealer_value}, with a full hand of {self.repr_hand(dealer_hand)}...")
            if player_value > dealer_value:
                BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, player, amount*2) # 2x because we took the original bet
                await ctx.send(f"... and loses to {player}, giving out {amount} chips!")
            elif player_value < dealer_value:
                await ctx.send(f"... and beats {player}, taking {amount} chips... better luck next hand!")
            else:
                BookKeeper.transfer_op(self.bot.book, HOUSE_NAME, player, amount) 
                await ctx.send(f"... and it's a push!")

        self.bot.game_registry["blackjack_hands"][player] = None

    @commands.command(name="stand")
    async def stand_command(self, ctx: commands.Context):
        player = ctx.author.name
        if not self.bot.game_registry["blackjack_hands"].get(player):
            await ctx.send(
                '"Seems like ya got nothing to stand on there, '
                f'{player}." Try !blackjack to start a new hand!'
            )
            return

        await self.player_stand(ctx)

    @commands.command(name="doubledown", aliases=["double-down", "double_down", "dd"])
    async def doubledown_command(self, ctx: commands.Context):
        player = ctx.author.name
        if not self.bot.game_registry["blackjack_hands"].get(player):
            await ctx.send(
                '"Seems like ya got nothing to double down on there, '
                f'{player}." Try !blackjack to start a new hand!'
            )
            return

        player_hand, dealer_hand, amount = self.bot.game_registry["blackjack_hands"][player]
        if (amount <= 0) or (amount>BookKeeper.check_op(self.bot.book, player, True)):
            await ctx.send(
                f'"I appreciate your resolve, {player}," The dealer says, '
                f'"but it seems like you got no chips to double down..." '
                f'"Could always wait for some cocktails though." he adds.'
            )
            return

        BookKeeper.transfer_op(self.bot.book, player, HOUSE_NAME, amount)
        self.bot.game_registry["blackjack_hands"][player] = (player_hand, dealer_hand, amount*2)
        await ctx.send(f"{player} doubles down into the hand with {amount} more chips!")
        
        # hit once when doubling down
        await self.player_hit(ctx)
        # if bust we are done
        if not self.bot.game_registry["blackjack_hands"].get(player):
            return
        # otherwise, stand and resolve
        await self.player_stand(ctx)

    @commands.command(name="diego")
    async def diego_command(self, ctx: commands.Context):
        player = ctx.author.name
        await ctx.send(f"Diego Sparx walks by, {player} asks for his divinations on the current blackjack deck...")
        if not player in self.bot.game_registry["blackjack_decks"]:
            await ctx.send('Diego looks on curiously, "but your sorry ass isn\'t even playing blackjack yet"?')
            return

        deck = self.bot.game_registry["blackjack_decks"][player]
        num_tens = len([c for c in deck if c[1]>=10])
        num_aces = len([c for c in deck if c[1]==1])
        num_cards_left = len(deck)
        await ctx.send(
            f"Diego Sparx squints, closes his eyes for a while, then whispers to {player}, "
            f'"I think there are {num_tens} ten/face cards and {num_aces} aces left in this {num_cards_left} card deck" '
            "as he walks back to his table."
        )

    @commands.cooldown(rate=10, per=900, bucket=commands.Bucket.member)
    @commands.command(name="blackjack")
    async def blackjack_command(self, ctx: commands.Context, amount: int):
        """
        initiate an 1v1 blackjack game against the house
        """
        player = ctx.author.name
        if (amount <= 0) or (amount>BookKeeper.check_op(self.bot.book, player, True)):
            await ctx.send(
                f'The dealer stares at {player} blankly and says, '
                '"how about just enjoying some cocktails for now if you don\'t got them chips?"'
            )
            return
        if not (self.BLACKJACK_BET_RANGE[0] <= amount <= self.BLACKJACK_BET_RANGE[1]):
            await ctx.send(
                f'The dealer points at the sign next to the table, '
                '"Sorry, our min and max bets are 100 and 2000 chips here, respectively"'
            )
            return
        if not player in self.bot.game_registry["blackjack_decks"]:
            await ctx.send(
                f'The dealer smiles, "Welcome, {player}, to the blackjack table!" '
                'We play 3 decks here, and we will shuffle when there are 26 cards left! '
                'For all the rules, please type `!help blackjack` to check them out!'
            )
            await ctx.send(self.shuffle_op(player))
        
        # make sure this money is no longer available to the player during the play
        BookKeeper.transfer_op(self.bot.book, player, HOUSE_NAME, amount)
        await self.new_hand_op(ctx, amount, player)


class VPSQ6Bot(commands.Bot):
    """
    """

    def __init__(self):
        super().__init__(token=ACCESS_TOKEN, prefix="!", initial_channels=["vpsqofficial"], nick="BarelyNoers")
        self.reminder.start()

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')

        await self.connected_channels[0].send("BarelyNoer's is now open for business! type !help to see what you can do to help Vinny...")

    @routines.routine(minutes=10, wait_first=True)
    async def reminder(self):
        await self.connected_channels[0].send("BarelyNoer's is currently open for business! type !help to see what you can do to help Vinny...")

    @commands.command()
    async def help(self, ctx: commands.Context, cmd: str | None):
        if not cmd:
            await ctx.send(
                "Welcome to BarelyNoer's! If you don't have an account with us yet, type !buyin to open an account! \n"
            )
            await ctx.send(
                "You can also type !check or !balance at any point to check how many chips someone has! \n"
            )

        if cmd == "blackjack":
            await ctx.send(
                "Blackjack at BarelyNoer's are played with 3 decks, you vs. the house one-on-one, shuffling happens when we get to 13 cards or fewer. "
                'No splitting, no surrendering, no insurances, natural blackjacks pay 2x your bet. '
                'Once you have a live hand, you may !hit, !stand or !doubledown. '
                'Today is your lucky day! BarelyNoers have a promotion going on -- '
                'if the cocktail lady is around, the natural blackjacks pay 8x your bet!'
            )
            await ctx.send(
                "To not spam the chat too much, you may play 10 hands every 15 minutes."
            )
            await ctx.send(
                'A faint voice whispers from across the halls, "you can *count* on me to double check your *cards* situation..." '
                'You\'d recognize the tone of Diego Sparx anywhere! type !diego to have Diego Sparx advise you!'
            )


if __name__ == "__main__":
    bot = VPSQ6Bot()
    bookkeeper_cog = BookKeeper(bot)
    bot.add_cog(bookkeeper_cog)
    special_events_cog = SpecialEvents(bot)
    bot.add_cog(special_events_cog)
    dealer_cog = Dealer(bot)
    bot.add_cog(dealer_cog)
    bot.run()