#!/usr/bin/env python3
# quarto.py
# Author: Quentin Lurkin & Kassabeh Zakariya & Jabbour Hanâ
# Version: May 17, 2018

import argparse
import socket
import sys
import random
import json
import copy
import re

from lib import game

class QuartoState(game.GameState):
    '''Class representing a state for the Quarto game.'''
    def __init__(self, initialstate=None, currentPlayer=None):
        self.__player = 0
        random.seed()
        if initialstate is None:
            pieces = []
            for shape in ['round', 'square']:
                for color in ['dark', 'light']:
                    for height in ['low', 'high']:
                        for filling in ['empty', 'full']:
                            pieces.append({
                                'shape': shape,
                                'color': color,
                                'height': height,
                                'filling': filling
                            })
            initialstate = {
                'board': [None] * 16,
                'remainingPieces': pieces,
                'pieceToPlay': None,
                'quartoAnnounced': False
            }

        if currentPlayer is None:
            currentPlayer = random.randrange(2)

        super().__init__(initialstate, currentPlayer=currentPlayer)

    def applymove(self, move):
        #{pos: 8, quarto: true, nextPiece: 2}
        stateBackup = copy.deepcopy(self._state)
        try:
            state = self._state['visible']
            if state['pieceToPlay'] is not None:
                try:
                    if state['board'][move['pos']] is not None:
                        raise game.InvalidMoveException('The position is not free')
                    state['board'][move['pos']] = state['remainingPieces'][state['pieceToPlay']]
                    del(state['remainingPieces'][state['pieceToPlay']])
                except game.InvalidMoveException as e:
                    raise e
                except:
                    raise game.InvalidMoveException("Your move should contain a \"pos\" key in range(16)")

            if len(state['remainingPieces']) > 0:
                try:
                    state['pieceToPlay'] = move['nextPiece']
                except:
                    raise game.InvalidMoveException("You must specify the next piece to play")
            else:
                state['pieceToPlay'] = None

            if 'quarto' in move:
                state['quartoAnnounced'] = move['quarto']
                winner = self.winner()
                if winner is None or winner == -1:
                    raise game.InvalidMoveException("There is no Quarto !")
            else:
                state['quartoAnnounced'] = False
        except game.InvalidMoveException as e:
            self._state = stateBackup
            raise e


    def _same(self, feature, elems):
        try:
            elems = list(map(lambda piece: piece[feature], elems))
        except:
            return False
        return all(e == elems[0] for e in elems)

    def _quarto(self, elems):
        return self._same('shape', elems) or self._same('color', elems) or self._same('filling', elems) or self._same('height', elems)

    def winner(self):
        state = self._state['visible']
        board = state['board']
        player = self._state['currentPlayer']

        # 00 01 02 03
        # 04 05 06 07
        # 08 09 10 11
        # 12 13 14 15

        if state['quartoAnnounced']:
            # Check horizontal and vertical lines
            for i in range(4):
                if self._quarto([board[4 * i + e] for e in range(4)]):
                    return player
                if self._quarto([board[4 * e + i] for e in range(4)]):
                    return player
            # Check diagonals
            if self._quarto([board[5 * e] for e in range(4)]):
                return player
            if self._quarto([board[3 + 3 * e] for e in range(4)]):
                return player
        return None if board.count(None) == 0 else -1

    def displayPiece(self, piece):
        if piece is None:
            return " " * 6
        bracket = ('(', ')') if piece['shape'] == "round" else ('[', ']')
        filling = 'E' if piece['filling'] == 'empty' else 'F'
        color = 'L' if piece['color'] == 'light' else 'D'
        format = ' {}{}{}{} ' if piece['height'] == 'low' else '{0}{0}{1}{2}{3}{3}'
        return format.format(bracket[0], filling, color, bracket[1])

    def prettyprint(self):
        state = self._state['visible']

        print('Board:')
        for row in range(4):
            print('|', end="")
            for col in range(4):
                print(self.displayPiece(state['board'][row*4+col]), end="|")
            print()

        print('\nRemaining Pieces:')
        print(", ".join([self.displayPiece(piece) for piece in state['remainingPieces']]))

        if state['pieceToPlay'] is not None:
            print('\nPiece to Play:')
            print(self.displayPiece(state['remainingPieces'][state['pieceToPlay']]))

    def nextPlayer(self):
        self._state['currentPlayer'] = (self._state['currentPlayer'] + 1) % 2


class QuartoServer(game.GameServer):
    '''Class representing a server for the Quarto game.'''
    def __init__(self, verbose=False):
        super().__init__('Quarto', 2, QuartoState(), verbose=verbose)

    def applymove(self, move):
        try:
            move = json.loads(move)
        except:
            raise game.InvalidMoveException('A valid move must be a valid JSON string')
        else:
            self._state.applymove(move)


class QuartoClient(game.GameClient):
    '''Class representing a client for the Quarto game.'''
    def __init__(self, name, server, verbose=False):
        super().__init__(server, QuartoState, verbose=verbose)
        self.__name = name

    def _handle(self, message):
        pass

    def _nextmove(self, state):
        visible = state._state['visible']
        move = {}

        # select the position were we'll put the piece given by the opponent
        if visible['pieceToPlay'] is not None:
            nextPosition(state)

        # select the next piece we'll give to the opponent
        nextPieceToGive(state)

        # apply the move to check for quarto
        # applymove will raise if we announce a quarto while there is not
        move['quarto'] = True
        try:
            state.applymove(move)
        except:
            del(move['quarto'])

        # send the move
        return json.dumps(move)

    def nextPosition(self,state) :
        """
        Select the position were we'll put the piece given by the opponent to make
        a quarto. If no quarto is possible then juste put it randomly.

        For each parameter of the piece to place we check if there's not already
        3 pieces with a commun parameter to place the piece at the remaining spot.
        If two places can make us win, because we only store one position in
        move['pos'] we may not have an issue. Also, no try except statement there
        because we do not apply(move).
        """

        visible = state._state['visible']
        move = {}
        countH,countV,countD1,countD2 = 0

        #low case
        if  bool(re.search("\[{1}",visible['pieceToPlay']) or bool(re.search("\({1}",visible['pieceToPlay']) :
            #No need to check were we can put the piece if there's no quarto possible
            if threeLow :
                for i in range(4) :
                #Horizontal check
                    for h in range(4):
                        if bool(re.search("\[{1}", board[4*i + h])) or bool(re.search("\({1}", board[4*i + h])) :
                            countH+=1
                        else :
                            emptySpot = 4*i+h
                        elif countH == 3 :
                            move['pos'] = emptySpot
                #Vertical check
                    for v in range(4):
                        if bool(re.search("\[{1}", board[4*v + i])) or bool(re.search("\({1}", board[4*v + i])) :
                            countV+=1
                        else :
                            emptySpot =4*v+i
                        elif countV == 3 :
                            move['pos'] = emptySpot
                #First diagonal check
                    for D1 in range(4):
                        if bool(re.search("\[{1}", board[5 * D1])) or bool(re.search("\({1}", board[5 * D1])) :
                            countD1+=1
                        else :
                            emptySpot =5*D1
                        elif countD1 == 3 :
                            move['pos'] = emptySpot
                #Second diagonal check
                    for D2 in range(4):
                        if bool(re.search("\[{1}", board[3 + 3*D2])) or bool(re.search("\({1}", board[3 + 3*D2])) :
                            countD2+=1
                        else :
                            emptySpot = 3 + 3*D2
                        elif countD2 == 3 :
                            move['pos'] = emptySpot
        #High case
        if  bool(re.search("\[{2}",visible['pieceToPlay']) or bool(re.search("\({2}",visible['pieceToPlay']) :
            if threeHigh :
                for i in range(4) :
                #Horizontal check
                    for h in range(4):
                        if bool(re.search("\[{2}", board[4*i + h])) or bool(re.search("\({2}", board[4*i + h])) :
                            countH+=1
                        else :
                            emptySpot = 4*i+h
                        elif countH == 3 :
                            move['pos'] = emptySpot
                #Vertical check
                    for v in range(4):
                        if bool(re.search("\[{2}", board[4*v + i])) or bool(re.search("\({2}", board[4*v + i])) :
                            countV+=1
                        else :
                            emptySpot =4*v+i
                        elif countV == 3 :
                            move['pos'] = emptySpot
                #First diagonal check
                    for D1 in range(4):
                        if bool(re.search("\[{2}", board[5 * D1])) or bool(re.search("\({2}", board[5 * D1])) :
                            countD1+=1
                        else :
                            emptySpot =5*D1
                        elif countD1 == 3 :
                            move['pos'] = emptySpot
                #Second diagonal check
                    for D2 in range(4):
                        if bool(re.search("\[{2}", board[3 + 3*D2])) or bool(re.search("\({2}", board[3 + 3*D2])) :
                            countD2+=1
                        else :
                            emptySpot = 3 + 3*D2
                        elif countD2 == 3 :
                            move['pos'] = emptySpot
        #Light case
        if  bool(re.search("L",visible['pieceToPlay']) :
            if threeLight :
                for i in range(4) :
                #Horizontal check
                    for h in range(4):
                        if bool(re.search("L", board[4*i + h])) :
                            countH+=1
                        else :
                            emptySpot = 4*i+h
                        elif countH == 3 :
                            move['pos'] = emptySpot
                #Vertical check
                    for v in range(4):
                        if bool(re.search("L", board[4*v + i])) :
                            countV+=1
                        else :
                            emptySpot =4*v+i
                        elif countV == 3 :
                            move['pos'] = emptySpot
                #First diagonal check
                    for D1 in range(4):
                        if bool(re.search("L", board[5 * D1])) :
                            countD1+=1
                        else :
                            emptySpot =5*D1
                        elif countD1 == 3 :
                            move['pos'] = emptySpot
                #Second diagonal check
                    for D2 in range(4):
                        if bool(re.search("L", board[3 + 3*D2])) :
                            countD2+=1
                        else :
                            emptySpot = 3 + 3*D2
                        elif countD2 == 3 :
                            move['pos'] = emptySpot
        #Dark case
        if  bool(re.search("D",visible['pieceToPlay']) :
            if threeLight :
                for i in range(4) :
                #Horizontal check
                    for h in range(4):
                        if bool(re.search("D", board[4*i + h])) :
                            countH+=1
                        else :
                            emptySpot = 4*i+h
                        elif countH == 3 :
                            move['pos'] = emptySpot
                #Vertical check
                    for v in range(4):
                        if bool(re.search("D", board[4*v + i])) :
                            countV+=1
                        else :
                            emptySpot =4*v+i
                        elif countV == 3 :
                            move['pos'] = emptySpot
                #First diagonal check
                    for D1 in range(4):
                        if bool(re.search("D", board[5 * D1])) :
                            countD1+=1
                        else :
                            emptySpot =5*D1
                        elif countD1 == 3 :
                            move['pos'] = emptySpot
                #Second diagonal check
                    for D2 in range(4):
                        if bool(re.search("D", board[3 + 3*D2])) :
                            countD2+=1
                        else :
                            emptySpot = 3 + 3*D2
                        elif countD2 == 3 :
                            move['pos'] = emptySpot
        #Full case
        if  bool(re.search("F",visible['pieceToPlay']) :
            if threeLight :
                for i in range(4) :
                #Horizontal check
                    for h in range(4):
                        if bool(re.search("F", board[4*i + h])) :
                            countH+=1
                        else :
                            emptySpot = 4*i+h
                        elif countH == 3 :
                            move['pos'] = emptySpot
                #Vertical check
                    for v in range(4):
                        if bool(re.search("F", board[4*v + i])) :
                            countV+=1
                        else :
                            emptySpot =4*v+i
                        elif countV == 3 :
                            move['pos'] = emptySpot
                #First diagonal check
                    for D1 in range(4):
                        if bool(re.search("F", board[5 * D1])) :
                            countD1+=1
                        else :
                            emptySpot =5*D1
                        elif countD1 == 3 :
                            move['pos'] = emptySpot
                #Second diagonal check
                    for D2 in range(4):
                        if bool(re.search("F", board[3 + 3*D2])) :
                            countD2+=1
                        else :
                            emptySpot = 3 + 3*D2
                        elif countD2 == 3 :
                            move['pos'] = emptySpot
        #Empty case
        if  bool(re.search("E",visible['pieceToPlay']) :
            if threeLight :
                for i in range(4) :
                #Horizontal check
                    for h in range(4):
                        if bool(re.search("E", board[4*i + h])) :
                            countH+=1
                        else :
                            emptySpot = 4*i+h
                        elif countH == 3 :
                            move['pos'] = emptySpot
                #Vertical check
                    for v in range(4):
                        if bool(re.search("E", board[4*v + i])) :
                            countV+=1
                        else :
                            emptySpot =4*v+i
                        elif countV == 3 :
                            move['pos'] = emptySpot
                #First diagonal check
                    for D1 in range(4):
                        if bool(re.search("E", board[5 * D1])) :
                            countD1+=1
                        else :
                            emptySpot =5*D1
                        elif countD1 == 3 :
                            move['pos'] = emptySpot
                #Second diagonal check
                    for D2 in range(4):
                        if bool(re.search("E", board[3 + 3*D2])) :
                            countD2+=1
                        else :
                            emptySpot = 3 + 3*D2
                        elif countD2 == 3 :
                            move['pos'] = emptySpot
        #Round case
        if  bool(re.search("\(",visible['pieceToPlay']) :
            if threeLight :
                for i in range(4) :
                #Horizontal check
                    for h in range(4):
                        if bool(re.search("\(", board[4*i + h])) :
                            countH+=1
                        else :
                            emptySpot = 4*i+h
                        elif countH == 3 :
                            move['pos'] = emptySpot
                #Vertical check
                    for v in range(4):
                        if bool(re.search("\(", board[4*v + i])) :
                            countV+=1
                        else :
                            emptySpot =4*v+i
                        elif countV == 3 :
                            move['pos'] = emptySpot
                #First diagonal check
                    for D1 in range(4):
                        if bool(re.search("\(", board[5 * D1])) :
                            countD1+=1
                        else :
                            emptySpot =5*D1
                        elif countD1 == 3 :
                            move['pos'] = emptySpot
                #Second diagonal check
                    for D2 in range(4):
                        if bool(re.search("\(", board[3 + 3*D2])) :
                            countD2+=1
                        else :
                            emptySpot = 3 + 3*D2
                        elif countD2 == 3 :
                            move['pos'] = emptySpot
        #Square case
        if  bool(re.search("\[",visible['pieceToPlay']) :
            if threeLight :
                for i in range(4) :
                #Horizontal check
                    for h in range(4):
                        if bool(re.search("\[", board[4*i + h])) :
                            countH+=1
                        else :
                            emptySpot = 4*i+h
                        elif countH == 3 :
                            move['pos'] = emptySpot
                #Vertical check
                    for v in range(4):
                        if bool(re.search("\[", board[4*v + i])) :
                            countV+=1
                        else :
                            emptySpot =4*v+i
                        elif countV == 3 :
                            move['pos'] = emptySpot
                #First diagonal check
                    for D1 in range(4):
                        if bool(re.search("\[", board[5 * D1])) :
                            countD1+=1
                        else :
                            emptySpot =5*D1
                        elif countD1 == 3 :
                            move['pos'] = emptySpot
                #Second diagonal check
                    for D2 in range(4):
                        if bool(re.search("\[", board[3 + 3*D2])) :
                            countD2+=1
                        else :
                            emptySpot = 3 + 3*D2
                        elif countD2 == 3 :
                            move['pos'] = emptySpot

    def nextPieceToGive(self,state) :
        """
        Function that decides which play we have to give the opponent.
        The strategy is to check if there's already 3 pieces ready to make a
        quarto so we don't give the last one.
        It's a def strategy.
        """

        visible = state._state['visible']
        move = {}
        save = visible['remainingPieces']

        if threeLow:
            for elem in save :
                if  bool(re.search("\[{1}", elem)) or bool(re.search("\({1}",elem) :
                    save.remove(elem)
        if threeHigh:
            for elem in save :
                if  bool(re.search("\[{2}", elem)) or bool(re.search("\({2}",elem) :
                    save.remove(elem)
        if threeEmpty:
            for elem in save :
                if  bool(re.search("E", elem)):
                    save.remove(elem)
        if threeFull :
            for elem in save :
                if  bool(re.search("F", elem)):
                    save.remove(elem)
        if threeDark :
            for elem in save :
                if  bool(re.search("D", elem)):
                    save.remove(elem)
        if threeLight :
            for elem in save :
                if  bool(re.search("L", elem)):
                    save.remove(elem)
        if threeRound :
            for elem in save :
                if  bool(re.search("\(", elem)):
                    save.remove(elem)
        if threeSquare :
            for elem in save :
                if  bool(re.search("\[", elem)):
                    save.remove(elem)
        try :
            #give the opponent a piece which will not let him win
            move['nextPiece'] = random.randint(0, len(save) - 1)
        except :
            #in the case that there's no more safe play, you've lost anyway so give a random piece
            move['nextPiece'] = random.randint(0, len(visible['remainingPieces']) - 1)

    def threeLow (self):
        #function that checks if 3 Low pieces are about to make a quarto
        #Return : True if yes
        #         False otherwise

        countH,countV,countD1,countD2 = 0
        for i in range(4) :
        #Horizontal check
            for h in range(4):
                if bool(re.search("\[{1}", board[4*i + h])) or bool(re.search("\({1}", board[4*i + h])) :
                    countH+=1
        #Vertical check
            for v in range(4):
                if bool(re.search("\[{1}", board[4*v + i])) or bool(re.search("\({1}", board[4*v + i])) :
                    countV+=1
        #First diagonal check
            for D1 in range(4):
                if bool(re.search("\[{1}", board[5 * D1])) or bool(re.search("\({1}", board[5 * D1])) :
                    countD1+=1
        #Second diagonal check
            for D2 in range(4):
                if bool(re.search("\[{1}", board[3 + 3*D2])) or bool(re.search("\({1}", board[3 + 3*D2])) :
                    countD2+=1

        if countH or countV or countD1 or countD2 == 3 :
            return True
        else :
            return False

    def threeHigh (self):
        #function that checks if 3 High pieces are about to make a quarto
        #Return : True if yes
        #         False otherwise

        countH,countV,countD1,countD2 = 0
        for i in range(4) :
        #Horizontal check
            for h in range(4):
                if bool(re.search("\[{2}", board[4*i + h])) or bool(re.search("\({2}", board[4*i + h])) :
                    countH+=1
        #Vertical check
            for v in range(4):
                if bool(re.search("\[{2}", board[4*v + i])) or bool(re.search("\({2}", board[4*v + i])) :
                    countV+=1
        #First diagonal check
            for D1 in range(4):
                if bool(re.search("\[{2}", board[5 * D1])) or bool(re.search("\({2}", board[5 * D1])) :
                    countD1+=1
        #Second diagonal check
            for D2 in range(4):
                if bool(re.search("\[{2}", board[3 + 3*D2])) or bool(re.search("\({2}", board[3 + 3*D2])) :
                    countD2+=1

        if countH or countV or countD1 or countD2 == 3 :
            return True
        else :
            return False

    def threeLight (self):
        #function that checks if 3 light pieces are about to make a quarto
        #Return : True if yes
        #         False otherwise

        countH,countV,countD1,countD2 = 0
        for i in range(4) :
        #Horizontal check
            for h in range(4):
                if bool(re.search("L", board[4*i + h])) :
                    countH+=1
        #Vertical check
            for v in range(4):
                if bool(re.search("L", board[4*v + i])):
                    countV+=1
        #First diagonal check
            for D1 in range(4):
                if bool(re.search("L", board[5 * D1])) :
                    countD1+=1
        #Second diagonal check
            for D2 in range(4):
                if bool(re.search("L", board[3 + 3*D2])) :
                    countD2+=1

        if countH or countV or countD1 or countD2 == 3 :
            return True
        else :
            return False

    def threeDark (self):
        #function that checks if 3 Dark pieces are about to make a quarto
        #Return : True if yes
        #         False otherwise

        countH,countV,countD1,countD2 = 0
        for i in range(4) :
        #Horizontal check
            for h in range(4):
                if bool(re.search("D", board[4*i + h])) :
                    countH+=1
        #Vertical check
            for v in range(4):
                if bool(re.search("D", board[4*v + i])):
                    countV+=1
        #First diagonal check
            for D1 in range(4):
                if bool(re.search("D", board[5 * D1])) :
                    countD1+=1
        #Second diagonal check
            for D2 in range(4):
                if bool(re.search("D", board[3 + 3*D2])) :
                    countD2+=1

        if countH or countV or countD1 or countD2 == 3 :
            return True
        else :
            return False

    def threeFull (self):
        #function that checks if 3 Fullfilled pieces are about to make a quarto
        #Return : True if yes
        #         False otherwise

        countH,countV,countD1,countD2 = 0
        for i in range(4) :
        #Horizontal check
            for h in range(4):
                if bool(re.search("F", board[4*i + h])) :
                    countH+=1
        #Vertical check
            for v in range(4):
                if bool(re.search("F", board[4*v + i])):
                    countV+=1
        #First diagonal check
            for D1 in range(4):
                if bool(re.search("F", board[5 * D1])) :
                    countD1+=1
        #Second diagonal check
            for D2 in range(4):
                if bool(re.search("F", board[3 + 3*D2])) :
                    countD2+=1

        if countH or countV or countD1 or countD2 == 3 :
            return True
        else :
            return False

    def threeEmpty (self):
        #function that checks if 3 Empty pieces are about to make a quarto
        #Return : True if yes
        #         False otherwise

        countH,countV,countD1,countD2 = 0
        for i in range(4) :
        #Horizontal check
            for h in range(4):
                if bool(re.search("E", board[4*i + h])) :
                    countH+=1
        #Vertical check
            for v in range(4):
                if bool(re.search("E", board[4*v + i])):
                    countV+=1
        #First diagonal check
            for D1 in range(4):
                if bool(re.search("E", board[5 * D1])) :
                    countD1+=1
        #Second diagonal check
            for D2 in range(4):
                if bool(re.search("E", board[3 + 3*D2])) :
                    countD2+=1

        if countH or countV or countD1 or countD2 == 3 :
            return True
        else :
            return False

    def threeRound (self):
        #function that checks if 3 Round shaped pieces are about to make a quarto
        #Return : True if yes
        #         False otherwise

        countH,countV,countD1,countD2 = 0
        for i in range(4) :
        #Horizontal check
            for h in range(4):
                if bool(re.search("\(", board[4*i + h])) :
                    countH+=1
        #Vertical check
            for v in range(4):
                if bool(re.search("\(", board[4*v + i])):
                    countV+=1
        #First diagonal check
            for D1 in range(4):
                if bool(re.search("\(", board[5 * D1])) :
                    countD1+=1
        #Second diagonal check
            for D2 in range(4):
                if bool(re.search("\(", board[3 + 3*D2])) :
                    countD2+=1

        if countH or countV or countD1 or countD2 == 3 :
            return True
        else :
            return False

    def threeSquare(self):
        #function that checks if 3 Square shaped pieces are about to make a quarto
        #Return : True if yes
        #         False otherwise

        countH,countV,countD1,countD2 = 0
        for i in range(4) :
        #Horizontal check
            for h in range(4):
                if bool(re.search("\[", board[4*i + h])) :
                    countH+=1
        #Vertical check
            for v in range(4):
                if bool(re.search("\[", board[4*v + i])):
                    countV+=1
        #First diagonal check
            for D1 in range(4):
                if bool(re.search("\[", board[5 * D1])) :
                    countD1+=1
        #Second diagonal check
            for D2 in range(4):
                if bool(re.search("\[", board[3 + 3*D2])) :
                    countD2+=1

        if countH or countV or countD1 or countD2 == 3 :
            return True
        else :
            return False

if __name__ == '__main__':
    # Create the top-level parser
    parser = argparse.ArgumentParser(description='Quarto game')
    subparsers = parser.add_subparsers(description='server client', help='Quarto game components', dest='component')
    # Create the parser for the 'server' subcommand
    server_parser = subparsers.add_parser('server', help='launch a server')
    server_parser.add_argument('--host', help='hostname (default: localhost)', default='localhost')
    server_parser.add_argument('--port', help='port to listen on (default: 5000)', default=5000)
    server_parser.add_argument('--verbose', action='store_true')
    # Create the parser for the 'client' subcommand
    client_parser = subparsers.add_parser('client', help='launch a client')
    client_parser.add_argument('name', help='name of the player')
    client_parser.add_argument('--host', help='hostname of the server (default: localhost)', default='127.0.0.1')
    client_parser.add_argument('--port', help='port of the server (default: 5000)', default=5000)
    client_parser.add_argument('--verbose', action='store_true')
    # Parse the arguments of sys.args
    args = parser.parse_args()
    if args.component == 'server':
        QuartoServer(verbose=args.verbose).run()
    else:
        QuartoClient(args.name, (args.host, args.port), verbose=args.verbose)
