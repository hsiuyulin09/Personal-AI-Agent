"""Parse local Conversation History commands without sending them to the LLM."""

from dataclasses import dataclass
import shlex
from string import hexdigits

from database.conversation_history.store import Conversation, ConversationMessage
from session_manager import DEFAULT_HISTORY_TURNS, SessionManager


# CLI 指令使用固定前綴，只有以 /session 開頭的輸入才由本檔處理。
# 其他文字會回傳 handled=False，讓 main.py 繼續交給一般對話流程。
SESSION_COMMAND = "/session"

# Session List 預設顯示 UUID 前 8 碼；搜尋短 ID 時也至少要求 8 碼，
# 避免 Session 增加後因前綴太短而經常命中多筆資料。
MIN_SHORT_ID_LENGTH = 8


@dataclass(frozen=True)
class CliCommandResult:
    # CLI Router 使用統一結果物件，main.py 不需要知道各指令的內部細節。
    # handled=False 表示這是一般對話，main.py 應繼續交給 system workflow。
    # handled=True 表示輸入已由 CLI 處理，output 可直接顯示且不應送進 LLM。
    handled: bool
    output: str = ""


class CliCommandError(ValueError):
    # 將「使用者輸入錯誤」和程式、Database 錯誤分開。
    # handle_cli_command 會把這類錯誤整理成可直接顯示的 CLI 訊息。
    """使用者輸入的 CLI 指令或參數無法執行。"""


def _display_title(conversation: Conversation) -> str:
    # Database 允許 title 為 None；顯示層再轉成容易辨識的文字，
    # 不把「未命名」寫回 Database，避免介面文字污染原始資料。
    return conversation.title or "(未命名)"


def _format_conversation(
    conversation: Conversation,
    current_session_id,
    full_id: bool = False,
) -> str:
    # 星號只代表執行期間目前使用的 Session，不是 Database 欄位。
    marker = "*" if conversation.session_id == current_session_id else " "
    session_id = str(conversation.session_id)

    # 預設輸出短 ID，使用 --full 時保留完整 UUID。
    if not full_id:
        session_id = session_id[:MIN_SHORT_ID_LENGTH]

    # isoformat 保留時區資訊，並將顯示精度固定到秒，避免輸出過長。
    updated_at = conversation.updated_at.isoformat(
        sep=" ",
        timespec="seconds",
    )
    return (
        f"{marker} {session_id}  "
        f"{_display_title(conversation)}  "
        f"updated: {updated_at}"
    )


def _format_history(messages: list[ConversationMessage]) -> str:
    # load_session_history 只回傳完整回合；沒有資料時提供明確狀態，
    # 不讓空字串看起來像是指令失敗。
    if not messages:
        return "目前沒有已完成的對話紀錄。"

    lines = []
    previous_turn_id = None

    for message in messages:
        # 同一個 turn_id 通常包含一筆 user 與一筆 assistant 訊息。
        # turn_id 改變時加入標題與空行，方便終端閱讀不同回合。
        if message.turn_id != previous_turn_id:
            if lines:
                lines.append("")
            lines.append(f"turn {str(message.turn_id)[:MIN_SHORT_ID_LENGTH]}")
            previous_turn_id = message.turn_id

        lines.append(f"{message.role}: {message.content}")

    return "\n".join(lines)


def _format_candidates(conversations: list[Conversation]) -> str:
    # Session title 可以重複，短 UUID 前綴也可能命中多筆。
    # 發生歧義時列出候選項目，讓使用者改用更長的 ID。
    return ", ".join(
        f"{str(conversation.session_id)[:MIN_SHORT_ID_LENGTH]} "
        f"({_display_title(conversation)})"
        for conversation in conversations
    )


def _looks_like_uuid_prefix(value: str) -> bool:
    # 搜尋時忽略 UUID 中的連字號，因此 12345678 與
    # 12345678-1234 都能和 UUID.hex 使用相同方式比對。
    normalized = value.replace("-", "")
    return (
        MIN_SHORT_ID_LENGTH <= len(normalized) <= 32
        and all(character in hexdigits for character in normalized)
    )


def _resolve_session(
    target: str,
    session_manager: SessionManager,
) -> Conversation:
    # 入口層負責把完整 UUID、短 UUID 或 title 轉成 Store 使用的完整 UUID。
    # Store 仍只接收 UUID，不需要理解 CLI 的短碼或 title 語法。
    normalized_target = target.strip()
    if not normalized_target:
        raise CliCommandError("請提供 Session ID 或 title。")

    conversations = session_manager.list_sessions()
    matches = []

    # 先收集 UUID 前綴符合的 Session。
    if _looks_like_uuid_prefix(normalized_target):
        uuid_prefix = normalized_target.replace("-", "").lower()
        matches.extend(
            conversation
            for conversation in conversations
            if conversation.session_id.hex.startswith(uuid_prefix)
        )

    # title 使用完整相等比對，不做模糊搜尋；這可以避免誤切換到名稱相近的 Session。
    matches.extend(
        conversation
        for conversation in conversations
        if conversation.title == normalized_target
        and conversation not in matches
    )

    if not matches:
        compact_target = normalized_target.replace("-", "")

        # 看起來是十六進位 ID、但不足 8 碼時，提供比「找不到」更精確的錯誤。
        if compact_target and all(character in hexdigits for character in compact_target):
            if len(compact_target) < MIN_SHORT_ID_LENGTH:
                raise CliCommandError(
                    f"短 Session ID 至少需要 {MIN_SHORT_ID_LENGTH} 碼。"
                )
        raise CliCommandError(f"找不到 Session：{normalized_target}")

    if len(matches) > 1:
        # 不自動挑選第一筆，避免改名或刪除錯誤的 Session。
        raise CliCommandError(
            "Session 識別值不唯一，請提供更長的 ID："
            f"{_format_candidates(matches)}"
        )

    return matches[0]


def _parse_history_limit(value: str | None) -> int | None:
    # 未輸入輪數時使用 SessionManager 的顯示預設值。
    if value is None:
        return DEFAULT_HISTORY_TURNS

    # CLI 的 all 是介面文字；Store 使用 None 表示不設定回合數上限。
    if value.casefold() == "all":
        return None

    # CLI 收到的內容都是字串，需先轉成 int 再交給 SessionManager。
    try:
        max_turns = int(value)
    except ValueError as error:
        raise CliCommandError("歷史輪數必須是正整數或 all。") from error

    if max_turns <= 0:
        raise CliCommandError("歷史輪數必須是正整數或 all。")

    return max_turns


def _is_history_limit(value: str) -> bool:
    # history 的單一參數可能是「Session 識別值」或「顯示輪數」。
    # 這個 helper 先判斷是否應把參數交給 _parse_history_limit。
    if value.casefold() == "all":
        return True

    try:
        int(value)
    except ValueError:
        return False
    return True


def _help_text() -> str:
    # 指令說明集中在一個函式，修改語法時不必散落到 main.py。
    return "\n".join([
        "Conversation History 指令：",
        "/session current",
        "/session list [--full]",
        "/session new [title]",
        "/session use <session_id|title> [turns|all]",
        "/session rename <session_id|title> <new_title>",
        "/session delete <session_id|title> --confirm",
        "/session history [session_id|title] [turns|all]",
        "/session help",
        "title 含空白時請使用引號，例如：\"研究筆記\"。",
    ])


def _handle_current(session_manager: SessionManager, arguments: list[str]) -> str:
    # current 只顯示 Session 資料，不讀取對話內容。
    if arguments:
        raise CliCommandError("current 不接受額外參數。")

    conversation = session_manager.get_current_session()
    return _format_conversation(
        conversation,
        session_manager.current_session_id,
        full_id=True,
    )


def _handle_help(session_manager: SessionManager, arguments: list[str]) -> str:
    # 每一個 handler 都使用相同的 (session_manager, arguments) 介面，
    # 因此 help 即使不使用 manager，也保留相同參數結構。
    if arguments:
        raise CliCommandError("help 不接受額外參數。")
    return _help_text()


def _handle_list(session_manager: SessionManager, arguments: list[str]) -> str:
    # list 預設顯示 8 碼短 ID；--full 可顯示 Database 保存的完整 UUID。
    if len(arguments) > 1 or (arguments and arguments[0] != "--full"):
        raise CliCommandError("用法：/session list [--full]")

    conversations = session_manager.list_sessions()
    full_id = arguments == ["--full"]
    lines = [
        _format_conversation(
            conversation,
            session_manager.current_session_id,
            full_id=full_id,
        )
        for conversation in conversations
    ]
    return "\n".join(lines) if lines else "目前沒有 Session。"


def _handle_new(session_manager: SessionManager, arguments: list[str]) -> str:
    # new 後方沒有文字時建立未命名 Session；有文字時合併成 title。
    # SessionManager.create_session 會同時把新 Session 設為目前 Session。
    title = " ".join(arguments).strip() or None
    conversation = session_manager.create_session(title)
    return "已建立並切換至 Session：\n" + _format_conversation(
        conversation,
        session_manager.current_session_id,
        full_id=True,
    )


def _handle_use(session_manager: SessionManager, arguments: list[str]) -> str:
    # use 先把 CLI 識別值解析成完整 Conversation，再呼叫 SessionManager 切換。
    if not 1 <= len(arguments) <= 2:
        raise CliCommandError(
            "用法：/session use <session_id|title> [turns|all]"
        )

    conversation = _resolve_session(arguments[0], session_manager)
    max_turns = _parse_history_limit(
        arguments[1] if len(arguments) == 2 else None
    )
    session_manager.switch_session(conversation.session_id)

    # 切換後載入的是終端顯示用歷史，不會改變送給 LLM 的 Context Window 上限。
    history = session_manager.load_session_history(
        conversation.session_id,
        max_turns,
    )

    return "\n".join([
        "已切換至 Session：",
        _format_conversation(
            conversation,
            session_manager.current_session_id,
            full_id=True,
        ),
        "",
        _format_history(history),
    ])


def _handle_rename(session_manager: SessionManager, arguments: list[str]) -> str:
    # 第一個參數用來尋找 Session，其餘文字合併成新的 title。
    if len(arguments) < 2:
        raise CliCommandError(
            "用法：/session rename <session_id|title> <new_title>"
        )

    conversation = _resolve_session(arguments[0], session_manager)
    new_title = " ".join(arguments[1:]).strip()
    renamed = session_manager.rename_session(
        conversation.session_id,
        new_title,
    )
    return "已重新命名 Session：\n" + _format_conversation(
        renamed,
        session_manager.current_session_id,
        full_id=True,
    )


def _handle_delete(session_manager: SessionManager, arguments: list[str]) -> str:
    # 刪除 Conversation 時 Database 會透過 ON DELETE CASCADE 一併刪除 messages。
    # 因此要求明確輸入 --confirm，降低誤刪完整對話歷史的風險。
    if len(arguments) != 2 or arguments[1] != "--confirm":
        raise CliCommandError(
            "刪除會連帶移除該 Session 的所有訊息。"
            "請使用：/session delete <session_id|title> --confirm"
        )

    conversation = _resolve_session(arguments[0], session_manager)
    deleted = session_manager.delete_session(conversation.session_id)
    if not deleted:
        raise CliCommandError("Session 不存在或未完成刪除。")

    # 如果刪除的是目前 Session，SessionManager 會自動取得或建立替代 Session。
    current = session_manager.get_current_session()
    return "\n".join([
        f"已刪除 Session：{conversation.session_id}",
        "目前 Session：",
        _format_conversation(
            current,
            session_manager.current_session_id,
            full_id=True,
        ),
    ])


def _handle_history(session_manager: SessionManager, arguments: list[str]) -> str:
    # 無參數：目前 Session 最近 DEFAULT_HISTORY_TURNS 輪。
    # 一個參數：可以是 turns、all，或另一個 Session 的識別值。
    # 兩個參數：指定 Session，再指定 turns 或 all。
    if len(arguments) > 2:
        raise CliCommandError(
            "用法：/session history [session_id|title] [turns|all]"
        )

    conversation = session_manager.get_current_session()
    max_turns = DEFAULT_HISTORY_TURNS

    if len(arguments) == 1:
        # 純整數或 all 被視為目前 Session 的顯示範圍；其他文字則視為 Session 識別值。
        if _is_history_limit(arguments[0]):
            max_turns = _parse_history_limit(arguments[0])
        else:
            conversation = _resolve_session(arguments[0], session_manager)
    elif len(arguments) == 2:
        conversation = _resolve_session(arguments[0], session_manager)
        max_turns = _parse_history_limit(arguments[1])

    history = session_manager.load_session_history(
        conversation.session_id,
        max_turns,
    )
    return "\n".join([
        _format_conversation(
            conversation,
            session_manager.current_session_id,
            full_id=True,
        ),
        "",
        _format_history(history),
    ])


def handle_cli_command(
    user_input: str,
    session_manager: SessionManager,
) -> CliCommandResult:
    """Handle one /session command; return handled=False for normal chat."""
    # 公開入口只接受原始輸入文字與已初始化的 SessionManager。
    # 本層不接收 ConnectionPool，也不直接執行 SQL。
    if not isinstance(user_input, str):
        raise TypeError("user_input must be str")

    stripped_input = user_input.strip()
    if not stripped_input:
        return CliCommandResult(handled=False)

    # 先做低成本的前綴判斷。不是 /session 就立即交還 main.py，
    # Skill、RAG 與一般聊天都不在這個 Router 內判斷。
    first_token = stripped_input.split(maxsplit=1)[0].casefold()
    if first_token != SESSION_COMMAND:
        return CliCommandResult(handled=False)

    # shlex.split 支援引號，因此含空白的 title 可寫成 "研究筆記"。
    try:
        tokens = shlex.split(stripped_input)
    except ValueError as error:
        return CliCommandResult(
            handled=True,
            output=f"指令格式錯誤：{error}",
        )

    if len(tokens) == 1:
        return CliCommandResult(handled=True, output=_help_text())

    command = tokens[1].casefold()
    arguments = tokens[2:]

    # dispatch table 將子指令名稱對應到 handler，避免堆疊大量 if/elif。
    # 新增 Conversation History 指令時，可在本檔新增 handler 並登錄於此。
    handlers = {
        "current": _handle_current,
        "list": _handle_list,
        "new": _handle_new,
        "use": _handle_use,
        "rename": _handle_rename,
        "delete": _handle_delete,
        "history": _handle_history,
        "help": _handle_help,
    }

    handler = handlers.get(command)
    if handler is None:
        return CliCommandResult(
            handled=True,
            output=f"未知的 Session 指令：{command}\n\n{_help_text()}",
        )

    # 只把使用者參數錯誤轉成 CLI 訊息；未預期的 Database／程式錯誤仍會向外拋出，
    # 讓 trace 與開發者能看見真正的故障，而不是被誤包裝成輸入錯誤。
    try:
        output = handler(session_manager, arguments)
    except (CliCommandError, TypeError, ValueError) as error:
        return CliCommandResult(
            handled=True,
            output=f"指令執行失敗：{error}",
        )

    # handled=True 告訴 main.py：顯示 output 後直接進入下一輪輸入，
    # 不呼叫 LLM，也不把這條管理指令寫進 Conversation History。
    return CliCommandResult(handled=True, output=output)
