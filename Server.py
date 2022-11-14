# Server to handle the UNO backend with websockets

import asyncio
import random
import socket
import websockets
import json

NUM_PLAYERS = 4
STARTING_CARDS = 7
players = []
deck = []
stack = []
currentPlayer = 0
# where the socket will be listening for messages
# get the current ip address of the computer
host = socket.gethostbyname(socket.gethostname())
port = 4000
print("Server started on " + host + ":" + str(port))

class Player:
    def __init__(self, name, websocket):
        self.name = name
        self.hand = []
        self.websocket = websocket

    def setWebsocket(self, websocket):
        self.websocket = websocket

    async def setHand(self, hand):
        self.hand = hand
        await self.websocket.send(json.dumps({"event": "HAND", "data": self.hand}))

    async def playCard(self, card):
        cardCopy = card.copy()
        if cardCopy["type"] == "wild":
            cardCopy["color"] = "-"
        self.hand.remove(cardCopy)
        await self.websocket.send(json.dumps({"event": "HAND", "data": self.hand}))

    async def send(self, event, data=None):
        await self.websocket.send(json.dumps({"event": event, "data": data}))

    async def recv(self):
        message = json.loads(await self.websocket.recv()) # {event, data}
        # if there is no data, set data to None
        if "data" not in message:
            message["data"] = None
        return message

async def handleNewConnection(websocket):
    name = json.loads(await websocket.recv())["data"]

    # check if player is already connected
    for p in players:
        if p.name == name:
            await websocket.send(json.dumps({"event": "ALREADY_CONNECTED"}))
            print("Player " + name + " already connected")
            websocket.close()
            return

    # if player is not reconnecting, add them to the list of players
    # check if there is room for the player
    if len(players) == NUM_PLAYERS:
        await websocket.send(json.dumps({"event": "FULL"}))
        print("Player " + name + " tried to connect but server is full")
        await websocket.close()
        return

    # add player to list of players
    player = Player(name, websocket)
    players.append(player)
    await websocket.send(json.dumps({"event": "CONNECTED"}))
    print("Player " + name + " connected")

    try:
        await websocket.wait_closed()
    except:
        print("hi")
    finally:
        print("Player " + name + " disconnected")
        players.remove(player)
        print("players left: " + str(len(players)))

def initializeDeck():
    global deck

    """
    Card: {
        type: "number" | "action" | "wild", 
        color: "red" | "blue" | "green" | "yellow" | "-", // "-" for wild cards wich color is to be determined
        value: "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "skip" | "reverse" | "draw2" | "wild" | "draw4"
        executed?: boolean // only used for action cards, true if the action has been executed so it wont activate again
    }
    """

    colors = ["red", "blue", "green", "yellow"]
    values = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
    actions = ["skip", "reverse", "draw2"]
    for color in colors:
        for value in values:
            # 2 of each card
            deck.append({"type": "number", "color": color, "value": value})
            deck.append({"type": "number", "color": color, "value": value})
        
        for action in actions:
            # 2 of each action card
            deck.append({"type": "action", "color": color, "value": action, "executed": False})
            deck.append({"type": "action", "color": color, "value": action, "executed": False})
            
    # 4 wild cards
    for i in range(4):
        deck.append({"type": "wild", "color": "-", "value": "wild"})
        deck.append({"type": "wild", "color": "-", "value": "draw4", "executed": False})

    # shuffle deck
    random.shuffle(deck)

def passTurn(direction: int):
    global currentPlayer
    currentPlayer += direction
    currentPlayer %= NUM_PLAYERS

async def sendToAllPlayers(event, data=None):
    for player in players:
        await player.send(event, data)

async def gameLoop():
    global deck, stack, players
    global currentPlayer
    direction = 1
    gameOver = False

    print("Game loop started")

    # way to send messages to all players
    # websockets.broadcast(set(map(lambda player: player.websocket, players)), "Hello")

    """
        send players board to all players
        tell all players the stack
        
        # Check the top card on the stack
        if it performs an action and the card has not been executed
            if it is a draw2
                tell current player to draw 2 cards and send them. {event: "DRAW2", data: [card1, card2]}
                tell all players that the current player has drawn 2 cards (the message will be displayed in the frontend as a notification right bottom) (event: "DRAWN", data: {player: "playerName", amount: 2})
            if it is a skip
                tell current player that they have been skipped (the message will be displayed in the frontend as an alert)
                tell all players that the current player has been skipped (the message will be displayed in the frontend as a notification right bottom)
            if it is a reverse
                tell all players that the direction has been reversed (the message will be displayed in the frontend as an alert)
                reverse the direction
            if it is a draw4
                tell current player to draw 4 cards and send them. {event: "DRAW4", data: [card1, card2, card3, card4]}
                tell all players that the current player has drawn 4 cards (the message will be displayed in the frontend as a notification right bottom) (event: "DRAWN", data: {player: "playerName", amount: 4})
            mark the card as executed
            continue to next player

        tell current player to play a card (event: TURN)
        turn loop:
            recieve a message from the current player (event and data)
            if the event is "DRAW" (message: {event: "DRAW"}):
                if the deck is empty reshuffle the stack
                send a message to the current player with the card drawn (message: {event: "CARD", data: card})
                continue
            if the event is "UNO" (message: {event: "UNO"}):
                if the player has only one card left:
                    tell all players that the current player has said UNO (the message will be displayed in the frontend as an alert)
                    mark the player as having said UNO
                    continue
            if the event is "PLAY" (message: {event: "PLAY", data: card}):
                if the card is not valid:
                    tell current player that the card is not valid (the message will be displayed in the frontend as an alert)
                    continue
                
                # it is a valid card then
                add the card to the stack
                update the player's hand
                if it is an action card:
                    mark the card as not executed
                
                if the player has one card left and has not said UNO:
                    send a message to the current player that they didnt say UNO (event: "UNO_PENALTY")
                    the player has to draw 2 cards
                    wait for player to send two "draw" petitions
                    tell all players that the current player didnt say UNO and has drawn 2 cards (the message will be displayed in the frontend as a notification right bottom)
                    break the turn loop

                if the player has no cards left:
                    tell all players that the current player has won (the message will be displayed in the frontend as an alert)
                    break the turn loop

                break the turn loop
                
    """

    # Game loop
    while not gameOver:
        # send stack to all players
        await sendToAllPlayers("STACK", stack[-1])
        # send player board to all players
        # {name, numCards, turn}[]. turn is 0: not turn, 1: turn, 2: next turn
        playerBoard = []
        for i in range(NUM_PLAYERS):
            playerBoard.append({"name": players[i].name, "numCards": len(players[i].hand), "turn": 0})
        playerBoard[currentPlayer]["turn"] = 1
        playerBoard[(currentPlayer + direction) % NUM_PLAYERS]["turn"] = 2
        await sendToAllPlayers("PLAYER_BOARD", playerBoard)

        # Check the top card on the stack
        if (stack[-1]["type"] == "action" or stack[-1]["value"] == "draw4") and not stack[-1]["executed"]:
            # Execute the action
            if stack[-1]["value"] == "draw2":
                # Tell the player he must draw two cards
                await players[currentPlayer].send("DRAW2")
                # Wait for the player to send a DRAW2 message
                while True:
                    message = await players[currentPlayer].recv()
                    if message["event"] == "DRAW2":
                        break
                # Send cards to player
                cards = [ deck.pop() for _ in range(2) ]
                await players[currentPlayer].send("DRAW", cards)
                # Add cards to player's hand
                players[currentPlayer].hand += cards
                # Tell all players that the current player has drawn 2 cards
                await sendToAllPlayers("DRAWN", {"player": players[currentPlayer].name, "amount": 2})
            elif stack[-1]["value"] == "skip":
                await sendToAllPlayers("SKIP", {"player": players[currentPlayer].name})
            elif stack[-1]["value"] == "reverse":
                await sendToAllPlayers("REVERSE")
                direction *= -1
                currentPlayer += direction
            elif stack[-1]["value"] == "draw4":
                # Tell the player he must draw four cards
                await players[currentPlayer].send("DRAW4")
                # Wait for the player to send a DRAW4 message
                while True:
                    message = await players[currentPlayer].recv()
                    if message["event"] == "DRAW4":
                        break
                # Send cards to player
                cards = [ deck.pop() for _ in range(4) ]
                await players[currentPlayer].send("DRAW", cards)
                # Add cards to player's hand
                players[currentPlayer].hand += cards
                # Tell all players that the current player has drawn 4 cards
                await sendToAllPlayers("DRAWN", {"player": players[currentPlayer].name, "amount": 4})
            stack[-1]["executed"] = True
            # send hand to current player
            passTurn(direction)
            continue

        # send turn to current player
        await players[currentPlayer].send("TURN")
        hasSaidUno = False
        while True:
            # receive message from current player
            message = await players[currentPlayer].recv()
            event = message["event"]
            data = message["data"]

            if event == "DRAW":
                # Draw a card
                card = deck.pop()
                await players[currentPlayer].send("DRAW", [card])
                # add the card to the player's hand
                players[currentPlayer].hand = [card] + players[currentPlayer].hand
                # Tell all players that the current player has drawn a card
                await sendToAllPlayers({"event": "DRAWN", "data": {"player": players[currentPlayer].name, "amount": 1}})
                # send board to all players
                await sendToAllPlayers("PLAYER_BOARD", playerBoard)

                continue
            elif event == "UNO":
                if len(players[currentPlayer].hand) == 2:
                    hasSaidUno = True
                    await sendToAllPlayers("UNO", {"player": players[currentPlayer].name})
                continue
            elif event == "PLAY":
                # check if card is valid
                if not isValidCard(data):
                    await players[currentPlayer].send("INVALID_CARD")
                    continue
                # remove card from player's hand
                await players[currentPlayer].playCard(data)
                # if its an action card, set executed to false
                if data["type"] == "action":
                    data["executed"] = False
                # add card to stack
                stack.append(data)

                # check if penalty needs to be applied
                if len(players[currentPlayer].hand) == 1 and not hasSaidUno:
                    # Draw 2 cards
                    cards = [ deck.pop() for _ in range(2) ]
                    await players[currentPlayer].send("UNO_PENALTY")
                    # Wait for the player to send a DRAW2 message
                    while True:
                        message = await players[currentPlayer].recv()
                        if message["event"] == "DRAW2":
                            break
                    # Send cards to player
                    await players[currentPlayer].send("DRAW", cards)
                    # Add cards to player's hand
                    players[currentPlayer].hand += cards
                    # Tell all players that the current player has drawn 2 cards
                    await sendToAllPlayers("DRAWN", {"player": players[currentPlayer].name, "amount": 2})
                    break
                # check if player has won
                if len(players[currentPlayer].hand) == 0:
                    await sendToAllPlayers("WINNER", {"player": players[currentPlayer].name})
                    gameOver = True
                    break
                break
        # send hand to current player
        passTurn(direction)

def isValidCard(card):
    global stack

    # check if card is a wild card
    if card["type"] == "wild":
        return True

    # check if card is same color or same value as top card on stack
    if card["color"] == stack[-1]["color"] or card["value"] == stack[-1]["value"]:
        return True

    return False

async def main():
    global deck, stack, players

    async with websockets.serve(handleNewConnection, host, port):
        # await asyncio.Future()

        # wait for all players to connect
        while len(players) < NUM_PLAYERS:
            await asyncio.sleep(1)

        # Initialize deck
        initializeDeck()

        # Randomize player order
        random.shuffle(players)

        # give each player their starting hand
        for player in players:
            await player.setHand(deck[:STARTING_CARDS])
            deck = deck[STARTING_CARDS:]

        # set the first card on the stack
        while True:
            card = deck.pop(0)
            if card["type"] != "wild":
                stack.append(card)
                break
            else:
                deck.append(card)

        # start game loop
        await gameLoop()

        # disconnect all players
        for player in players:
            await player.websocket.close()

if __name__ == "__main__":
    asyncio.run(main())