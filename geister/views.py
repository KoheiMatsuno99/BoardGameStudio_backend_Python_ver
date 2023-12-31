from collections import OrderedDict
from typing import Optional, Tuple
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request

from .geister import Table, Player, Piece, Block
from .serializers import (
    PlayerSerializer,
    TableSerializer,
    PieceSerializer,
    BlockSerializer,
)

from .models import GameState


@api_view(["GET"])
def test(request: Request) -> Response:
    return Response({"message": "Hello, world!"}, status=status.HTTP_200_OK)


@api_view(["POST"])
def start_game(request: Request) -> Response:
    player_data = request.data
    print(player_data)
    player_serializer = PlayerSerializer(data=player_data, many=True)
    if player_serializer.is_valid():
        players = player_serializer.save()
        table = Table(players)
        # オフラインモードのみplayer[1]がcpu固定なので、cpuの初期配置を行う
        table.initialize_cpu_pieces_position()
        table_serializer = TableSerializer(table)
        serialized_data = table_serializer.data
        game_state = GameState(
            players=serialized_data["players"],
            table=serialized_data["table"],
            winner=serialized_data["winner"],
            turn=serialized_data["turn"],
        )
        game_state.save()
        print(game_state.id)
        serialized_data_with_id = {**serialized_data, "id": game_state.id}
        return Response(serialized_data_with_id, status=status.HTTP_201_CREATED)
    else:
        return Response(player_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def get_ready(request: Request, game_id: int) -> Response:
    print("Received data of initial positions")
    print("----------")
    print("----------")
    print("request.data")
    print(request.data)
    print("----------")
    print("----------")
    current_table_data = GameState.objects.get(id=game_id)
    # request.dataで受け取ったデータをcurrent_table_dataに反映させる
    current_table_data.players = request.data.get("players")
    current_table_data.table = request.data.get("table")
    current_table_data.winner = request.data.get("winner")
    current_table_data.turn = request.data.get("turn")
    print(current_table_data)
    current_table_data.save()
    # current_table_dataをシリアライズして返す
    new_table_data = {
        "players": current_table_data.players,
        "winner": current_table_data.winner,
        "table": current_table_data.table,
        "turn": current_table_data.turn,
    }
    print("----------")
    print("----------")
    print("new data is following this;")
    print("----------")
    print(new_table_data)
    print("----------")
    print("----------")
    table_serializer = TableSerializer(data=new_table_data)
    if table_serializer.is_valid():
        updated_table = table_serializer.save()
        updated_table_serializer = TableSerializer(updated_table)
        return Response(updated_table_serializer.data, status=status.HTTP_200_OK)
    else:
        return Response(table_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def get_table_serializer(
    data: dict,
) -> Tuple[Optional[Table], Optional[Response]]:
    table_serializer = TableSerializer(data=data)
    if table_serializer.is_valid():
        return table_serializer.create(table_serializer.validated_data), None
    else:
        return None, Response(
            table_serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )


def get_players_serializer(
    data: list[dict],
) -> Tuple[Optional[list[Player]], Optional[Response]]:
    player_serializer = PlayerSerializer(data=data, many=True)
    if player_serializer.is_valid():
        players_data = player_serializer.validated_data
        players = []
        for player_data in players_data:
            pieces = {k: Piece(**v) for k, v in player_data["pieces"].items()}
            player = Player(name=player_data["name"], pieces=pieces)
            players.append(player)
        return players, None
    else:
        return None, Response(
            player_serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )


def get_piece_serializer(
    data: dict,
) -> Tuple[Optional[Piece], Optional[Response]]:
    piece_serializer = PieceSerializer(data=data)
    if piece_serializer.is_valid(raise_exception=True):
        piece_data = piece_serializer.validated_data
        piece = Piece(**piece_data)
        return piece, None
    else:
        return None, Response(
            piece_serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )


def get_block_serializer(
    data: dict,
) -> Tuple[Optional[Block], Optional[Response]]:
    block_serializer = BlockSerializer(data=data)
    if block_serializer.is_valid():
        block_data = block_serializer.validated_data
        block = Block(**block_data)
        return block, None
    else:
        return None, Response(
            block_serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )


def get_piece_key_from_players(
    players_data: list[dict], piece_key: str
) -> Tuple[Optional[dict], Optional[Response]]:
    for player in players_data:
        if piece_key in player["pieces"]:
            return player["pieces"][piece_key], None
    return None, Response(
        {"error": "piece_key not found"}, status=status.HTTP_400_BAD_REQUEST
    )


@api_view(["POST"])
def move_piece(request: Request, game_id: int) -> Response:
    current_table = GameState.objects.get(id=game_id)
    current_table_data = {
        "players": current_table.players,
        "winner": current_table.winner,
        "table": current_table.table,
        "turn": current_table.turn,
    }
    table, error_response = get_table_serializer(current_table_data)
    if error_response:
        return error_response
    if table is None:
        return Response(
            {"detail": "falied table deserialize"}, status=status.HTTP_400_BAD_REQUEST
        )

    if error_response:
        return error_response

    piece_key = request.data["piece_key"]

    player_piece, error_response = get_piece_serializer(request.data["player_piece"])
    if error_response:
        return error_response
    if player_piece is None:
        return Response(
            {"detail": "request.data['player_piece'] is None"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    print("request.data['destination']", request.data["destination"])
    destination, error_response = get_block_serializer(request.data["destination"])

    if error_response:
        return error_response
    if destination is None:
        return Response(
            {"detail": "request.data['destination'] is None"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if destination.piece is not None:
        # リクエストからとってきているのでdestination.pieceはPiece型ではなくOrderedDict型
        if isinstance(destination.piece, OrderedDict):
            target, error_response = get_piece_serializer(destination.piece)
        # destination.pieceがtargetなので、シリアライズが正しく行われていればtargetがNoneになることはない
        if target is None:
            return Response(
                {"detail": "target is None"}, status=status.HTTP_400_BAD_REQUEST
            )
        if target.get_owner() != player_piece.get_owner():
            table.pick(destination, target)
    table.move(player_piece, piece_key, destination)
    table.switch_turn()

    updated_table = TableSerializer(table).data
    # updated_tableの内容をDBに保存
    current_table.players = updated_table["players"]
    current_table.winner = updated_table["winner"]
    current_table.table = updated_table["table"]
    current_table.turn = updated_table["turn"]
    current_table.save()
    return Response(updated_table, status=status.HTTP_200_OK)


@api_view(["POST"])
def cpu_move_piece(request: Request, game_id: int) -> Response:
    current_table = GameState.objects.get(id=game_id)
    current_table_data = {
        "players": current_table.players,
        "winner": current_table.winner,
        "table": current_table.table,
        "turn": current_table.turn,
    }
    table, error_response = get_table_serializer(current_table_data)
    if error_response:
        return error_response
    if table is None:
        return Response(
            {"detail": "failed deserialize"}, status=status.HTTP_400_BAD_REQUEST
        )
    table.cpu_move()
    table.switch_turn()
    updated_table = TableSerializer(table).data
    # updated_tableの内容をDBに保存
    current_table.players = updated_table["players"]
    current_table.winner = updated_table["winner"]
    current_table.table = updated_table["table"]
    current_table.turn = updated_table["turn"]
    current_table.save()
    return Response(updated_table, status=status.HTTP_200_OK)
