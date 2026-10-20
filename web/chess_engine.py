''' Essa classe é a responsável por guardar toda a informação sobre o estado atual do jogo,
e também é responsável por determinar os movimentos válidos do jogo '''

class GameState():
    def __init__(self):
        # A tábua é possui lista de 8x8 e cada casa possui um elemento de dois caractere
        # O primeiro caractere representa a cor da peça "W" para white(Branco) e "B" para Black(Preto)
        # O segundo caractere representa o tipo da peça nas seguinte ordem: Torre, Cavalo, Bispo, Rainha, Rei, Bispo, Cavalo, Torre
        # '--' significa espaço vazio
        # Na versão web o estado fica no servidor, então a tábua mora aqui e não no socket
        self.board = [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
            ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
        ]
        self.whiteToMove = True

        self.moveLog = []
        self.moveFunctions = {'P': self.getPawnMoves, 'R': self.getRookMoves, 'N': self.getKnightMoves,
                              'B': self.getBishopMoves, 'Q': self.getQueenMoves, 'K': self.getKingMoves}
        # usado para identificar checks validos ou invalidos
        self.whiteKingLocation = (7, 4)
        self.blackKingLocation = (0, 4)

        self.checkMate = False
        self.stalemate = False

        self.enpassantPossible = ()  # cordinadas para o quadrado onde o en passant é possivel

        self.currentCastlingRight = castleRights(True, True, True, True)
        self.castleRightsLog = [castleRights(self.currentCastlingRight.wks, self.currentCastlingRight.bks,
                                             self.currentCastlingRight.wqs, self.currentCastlingRight.bqs)]

    def makeMove(self, move):  # Faz os movimentos
        # movendo a peça
        self.board[move.endRow][move.endCol] = move.pieceMoved
        # faz o quadrado começar vazio
        self.board[move.startRow][move.startCol] = '--'
        self.moveLog.append(move)
        self.whiteToMove = not self.whiteToMove  # mudando os turnos
        # checando se os reis foram movidos para atualizar sua localização
        if move.pieceMoved == 'wK':
            self.whiteKingLocation = (move.endRow, move.endCol)
        elif move.pieceMoved == 'bK':
            self.blackKingLocation = (move.endRow, move.endCol)

        # promoção do peao
        if move.isPawnPromotion:
            self.board[move.endRow][move.endCol] = move.pieceMoved[0] + 'Q'

        # enpassant
        if move.isEnpassantMove:
            self.board[move.startRow][move.endCol] = '--'
        if move.pieceMoved[1] == 'P' and abs(move.startRow - move.endRow) == 2:
            self.enpassantPossible = (
                (move.startRow + move.endRow) // 2, move.startCol)
        else:
            self.enpassantPossible = ()
        # movimento roque (castle)
        if move.isCastleMove:
            # movimento roque (castle) no lado do rei
            if move.endCol - move.startCol == 2:
                self.board[move.endRow][move.endCol -
                                               1] = self.board[move.endRow][move.endCol+1]
                self.board[move.endRow][move.endCol+1] = '--'
            else:  # movimento roque (castle) no lado da rainha
                self.board[move.endRow][move.endCol +
                                               1] = self.board[move.endRow][move.endCol-2]
                self.board[move.endRow][move.endCol-2] = '--'

        # atualiza o castling rights - sempre que um rei ou torre for movida
        self.updateCastleRights(move)
        self.castleRightsLog.append(castleRights(self.currentCastlingRight.wks, self.currentCastlingRight.bks,
                                                 self.currentCastlingRight.wqs, self.currentCastlingRight.bqs))

    def undoMove(self):  # desfazendo o movimento
        if len(self.moveLog) != 0:  # certificando que tem um movimento para desfazer
            move = self.moveLog.pop()  # voltando a açao
            self.board[move.startRow][move.startCol] = move.pieceMoved
            self.board[move.endRow][move.endCol] = move.pieceCaptured
            self.whiteToMove = not self.whiteToMove   # trocando o turno
            # checando se os reis foram movidos para atualizar sua localização
            if move.pieceMoved == 'wK':
                self.whiteKingLocation = (move.startRow, move.startCol)
            elif move.pieceMoved == 'bK':
                self.blackKingLocation = (move.startRow, move.startCol)

            # desfazendo o movimento de enpassant
            if move.isEnpassantMove:
                self.board[move.endRow][move.endCol] = '--'
                self.board[move.startRow][move.endCol] = move.pieceCaptured
                self.enpassantPossible = (move.endRow, move.endCol)
            # desfaz um avanço de peão de 2 casas
            if move.pieceMoved[1] == 'P' and abs(move.startRow - move.endRow) == 2:
                self.enpassantPossible = ()

            # desfazendo o movimento castle
            if move.isCastleMove:
                if move.endCol - move.startCol == 2:  # lado do rei
                    self.board[move.endRow][move.endCol +
                                                   1] = self.board[move.endRow][move.endCol-1]
                    self.board[move.endRow][move.endCol-1] = '--'
                else:  # lado da rainha
                    self.board[move.endRow][move.endCol -
                                                   2] = self.board[move.endRow][move.endCol+1]
                    self.board[move.endRow][move.endCol+1] = '--'

            # desfazendo castling rights
            self.castleRightsLog.pop()
            # cópia para não alterar o registro do log quando o roque for atualizado depois
            last = self.castleRightsLog[-1]
            self.currentCastlingRight = castleRights(last.wks, last.bks, last.wqs, last.bqs)

    # atualiza o castle rights (roque) á peça movida
    def updateCastleRights(self, move):
        if move.pieceMoved == 'wK':
            self.currentCastlingRight.wks = False
            self.currentCastlingRight.wqs = False
        elif move.pieceMoved == 'bK':
            self.currentCastlingRight.bks = False
            self.currentCastlingRight.bqs = False
        elif move.pieceMoved == 'wR':
            if move.startRow == 7:
                if move.startCol == 0:  # torre da esquerda
                    self.currentCastlingRight.wqs = False
                elif move.startCol == 7:  # torre da direita
                    self.currentCastlingRight.wks = False

        elif move.pieceMoved == 'bR':
            if move.startRow == 0:
                if move.startCol == 0:
                    self.currentCastlingRight.bqs = False  # torre da esquerda
                elif move.startCol == 7:
                    self.currentCastlingRight.bks = False  # torre da direita

    def getValidMoves(self):  # todos os movimentos validos (maquina)
        tempEnpassantPossible = self.enpassantPossible
        tempCastleRights = castleRights(self.currentCastlingRight.wks, self.currentCastlingRight.bks,
                                        self.currentCastlingRight.wqs, self.currentCastlingRight.bqs)
        # pega todos os movimentos
        moves = self.getAllPossibleMoves()

        if self.whiteToMove:
            self.getCastleMoves(
                self.whiteKingLocation[0], self.whiteKingLocation[1], moves)
        else:
            self.getCastleMoves(
                self.blackKingLocation[0], self.blackKingLocation[1], moves)

        # retrocede na lista
        for i in range(len(moves)-1, -1, -1):
            # faz o movimento e troca de turno
            self.makeMove(moves[i])
            self.whiteToMove = not self.whiteToMove
            if self.inCheck():
                # vê se o movimento anterior coloca o jogador em xeque
                moves.remove(moves[i])
            # troca de turno e desfaz o movimento
            self.whiteToMove = not self.whiteToMove
            self.undoMove()
        # verifica se não há movimentos válidos (seja: impasse ou xeque-mate)
        if len(moves) == 0:
            # vê se está em xeque ou impasse
            if self.inCheck():
                self.checkMate = True
            else:
                self.stalemate = True
        else:
            self.checkMate = False
            self.stalemate = False

        # todos os movimentos validos
        self.enpassantPossible = tempEnpassantPossible
        self.currentCastlingRight = tempCastleRights
        return moves

    def inCheck(self):
        # verifica qual o turno
        if self.whiteToMove:
            # retorna um booleano e verifica se o rei branco está sob ataque
            return self.squareUnderAttack(self.whiteKingLocation[0], self.whiteKingLocation[1])
        else:
            # quando o rei preto esta em cheque
            return self.squareUnderAttack(self.blackKingLocation[0], self.blackKingLocation[1])

    def squareUnderAttack(self, r, c):
        # ve os movimentos do oponente mudando o turno, pegando todos os movimentos e mundando o turno novamente
        self.whiteToMove = not self.whiteToMove
        oppMoves = self.getAllPossibleMoves()
        self.whiteToMove = not self.whiteToMove
        # verifica todos os movimentos e ve se o ultimo quadrado é um quadrado interado na função
        for move in oppMoves:
            if move.endRow == r and move.endCol == c:
                return True
        return False

    def getAllPossibleMoves(self):  # todos os movimentos possiveis
        moves = []
        for r in range(len(self.board)):  # numeros de linhas
            # numeros de coluna da linha
            for c in range(len(self.board[r])):
                turn = self.board[r][c][0]
                # checando a cor da peça
                if (turn == 'w' and self.whiteToMove) or (turn == 'b' and not self.whiteToMove):
                    piece = self.board[r][c][1]
                    self.moveFunctions[piece](r, c, moves)
        return moves

    def getPawnMoves(self, r, c, moves):
        # Movimento da peça branca
        if self.whiteToMove:
            # checando se o quadrado está vazio
            if self.board[r-1][c] == '--':
                moves.append(Move((r, c), (r-1, c), self.board))
                if r == 6 and self.board[r-2][c] == '--':
                    moves.append(Move((r, c), (r-2, c), self.board))
            # capturando para esquerda
            if c - 1 >= 0:
                if self.board[r-1][c-1][0] == 'b':
                    moves.append(Move((r, c), (r-1, c-1), self.board))
                elif (r-1, c-1) == self.enpassantPossible:
                    moves.append(
                        Move((r, c), (r-1, c-1), self.board, isEnpassantMove=True))
            # capturando para direita
            if c + 1 <= 7:
                if self.board[r-1][c+1][0] == 'b':
                    moves.append(Move((r, c), (r-1, c+1), self.board))
                elif (r-1, c+1) == self.enpassantPossible:
                    moves.append(
                        Move((r, c), (r-1, c+1), self.board, isEnpassantMove=True))

        # Movimento da peça preta
        else:
            if self.board[r + 1][c] == '--':
                # checando se o quadrado está vazio
                moves.append(Move((r, c), (r + 1, c), self.board))
                if r == 1 and self.board[r + 2][c] == '--':
                    moves.append(Move((r, c), (r+2, c), self.board))
            # capturando para esquerda
            if c - 1 >= 0:
                if self.board[r + 1][c - 1][0] == 'w':
                    moves.append(Move((r, c), (r + 1, c-1), self.board))
                elif (r + 1, c - 1) == self.enpassantPossible:
                    moves.append(Move((r, c), (r + 1, c - 1),
                                 self.board, isEnpassantMove=True))
            # capturando para direita
            if c + 1 <= 7:
                if self.board[r + 1][c + 1][0] == 'w':
                    moves.append(Move((r, c), (r+1, c+1), self.board))
                elif (r + 1, c + 1) == self.enpassantPossible:
                    moves.append(Move((r, c), (r + 1, c + 1),
                                 self.board, isEnpassantMove=True))

    def getRookMoves(self, r, c, moves):
        # cima baixo direita e esquerda
        directions = ((-1, 0), (0, -1), (1, 0), (0, 1))
        oppColour = 'b' if self.whiteToMove else 'w'
        # passa por cada direção
        for d in directions:
            # faz um loop 8 vezes o comprimento/largura do tabuleiro, pois uma torre pode se mover 8 casas
            for i in range(1, 8):
                endRow = r + d[0] * i
                endCol = c + d[1] * i
                if 0 <= endRow < 8 and 0 <= endCol < 8:
                    endPiece = self.board[endRow][endCol]
                    if endPiece == '--':  # Espaço vazio válido
                        moves.append(
                            Move((r, c), (endRow, endCol), self.board))
                    elif endPiece[0] == oppColour:
                        moves.append(
                            Move((r, c), (endRow, endCol), self.board))
                        break
                    else:  # peça amiga invalida
                        break
                # movimento fora da tábua
                else:
                    break

    def getBishopMoves(self, r, c, moves):
        # direções em que o bispo pode se mover (diagonais)
        directions = ((-1, -1), (1, -1), (1, 1), (-1, 1))
        oppColour = 'b' if self.whiteToMove else 'w'
        # passa por cada direção
        for d in directions:
            # interage 8 vezes
            for i in range(1, 8):
                endRow = r + d[0] * i
                endCol = c + d[1] * i
                if 0 <= endRow < 8 and 0 <= endCol < 8:
                    endPiece = self.board[endRow][endCol]
                    if endPiece == '--':  # Espaço vazio válido
                        moves.append(
                            Move((r, c), (endRow, endCol), self.board))
                    # se houver uma peça do oponente, podemos pegá-la e sair dessa direção
                    elif endPiece[0] == oppColour:
                        moves.append(
                            Move((r, c), (endRow, endCol), self.board))
                        break
                    # peça amiga invalida
                    else:
                        break
                # movimento fora da tábua
                else:
                    break

    def getQueenMoves(self, r, c, moves):
        self.getRookMoves(r, c, moves)
        self.getBishopMoves(r, c, moves)

    def getKnightMoves(self, r, c, moves):
        knightMoves = ((-2, -1), (-2, 1), (-1, -2), (-1, 2),
                       (1, -2), (1, 2), (2, -1), (2, 1))
        allyColour = 'w' if self.whiteToMove else 'b'
        for m in knightMoves:
            endRow = r + m[0]
            endCol = c + m[1]
            if 0 <= endRow < 8 and 0 <= endCol < 8:
                endPiece = self.board[endRow][endCol]
                if endPiece[0] != allyColour:
                    moves.append(
                        Move((r, c), (endRow, endCol), self.board))

    def getKingMoves(self, r, c, moves):
        directions = ((-1, -1), (1, -1), (1, 1), (-1, 1),
                      (-1, 0), (0, -1), (1, 0), (0, 1))
        allyColour = 'w' if self.whiteToMove else 'b'
        for d in directions:
            endRow = r + d[0]
            endCol = c + d[1]
            if 0 <= endRow < 8 and 0 <= endCol < 8:
                endPiece = self.board[endRow][endCol]
                # Não for um aliado (casa vazia ou peça inimiga)
                if endPiece[0] != allyColour:
                    moves.append(
                        Move((r, c), (endRow, endCol), self.board))

    def getCastleMoves(self, r, c, moves):
        # não posso fazer castle se um quadrado estiver sob ataque
        if self.squareUnderAttack(r, c):
            return
        # pode se mover para lá
        if (self.whiteToMove and self.currentCastlingRight.wks) or (not self.whiteToMove and self.currentCastlingRight.bks):
            self.getKingsideCastleMoves(r, c, moves)
        if (self.whiteToMove and self.currentCastlingRight.wqs) or (not self.whiteToMove and self.currentCastlingRight.bqs):
            self.getQueensideCastleMoves(r, c, moves)

    def getKingsideCastleMoves(self, r, c, moves):
        if self.board[r][c + 1] == '--' and self.board[r][c + 2] == '--':
            if not self.squareUnderAttack(r, c + 1) and not self.squareUnderAttack(r, c + 2):
                moves.append(
                    Move((r, c), (r, c + 2), self.board, isCastleMove=True))

    def getQueensideCastleMoves(self, r, c, moves):
        if self.board[r][c - 1] == '--' and self.board[r][c - 2] == '--' and self.board[r][c - 3] == '--':
            if not self.squareUnderAttack(r, c - 1) and not self.squareUnderAttack(r, c - 2):
                moves.append(
                    Move((r, c), (r, c - 2), self.board, isCastleMove=True))


class castleRights():

    def __init__(self, wks, bks, wqs, bqs):
        self.wks = wks
        self.bks = bks
        self.wqs = wqs
        self.bqs = bqs


class Move():
    # Numerando as linhas e colunas de 1 a 8
    ranksToRows = {"1": 7, "2": 6, "3": 5, "4": 4,
                   "5": 3, "6": 2, "7": 1, "8": 0}
    rowsToRanks = {v: k for k, v in ranksToRows.items()}

    filesToCols = {"a": 0, "b": 1, "c": 2, "d": 3,
                   "e": 4, "f": 5, "g": 6, "h": 7}
    colsToFiles = {v: k for k, v in filesToCols.items()}

    def __init__(self, startSq, endSq, board, isEnpassantMove=False, isCastleMove=False):
        # começo e fim da localizaçao/quadrado
        self.startRow = startSq[0]
        self.startCol = startSq[1]
        self.endRow = endSq[0]
        self.endCol = endSq[1]
        # Onde a peça estava
        self.pieceMoved = board[self.startRow][self.startCol]
        # Onde a peça será movida
        self.pieceCaptured = board[self.endRow][self.endCol]
        # booleano para ver se o peão preto ou branco foi movido para a linha final
        self.isPawnPromotion = ((self.pieceMoved == 'wP' and self.endRow == 0) or (
            self.pieceMoved == 'bP' and self.endRow == 7))

        self.isEnpassantMove = isEnpassantMove

        if self.isEnpassantMove:
            self.pieceCaptured = 'wP' if self.pieceMoved == 'bP' else 'bP'

        self.isCastleMove = isCastleMove

        # comparando os movimentos
        self.moveID = self.startRow * 1000 + self.startCol * \
            100 + self.endRow * 10 + self.endCol

    # igualdade do objeto da class move
    def __eq__(self, other):
        if isinstance(other, Move):
            return self.moveID == other.moveID

    # Essa função retorna a posição da casa e da coluna
    def getChessNot(self):
        return self.getRankFile(self.startRow, self.startCol) + self.getRankFile(self.endRow, self.endCol)

    def getRankFile(self, r, c):
        return self.colsToFiles[c] + self.rowsToRanks[r]
