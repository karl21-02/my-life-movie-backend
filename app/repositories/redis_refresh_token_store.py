import json
from datetime import datetime, timezone
from typing import Any

from redis import Redis
from redis.exceptions import WatchError

from app.models.auth_refresh_token import AuthRefreshToken, RefreshTokenStatus
from app.repositories.refresh_token_store import (
    RefreshTokenMetadata,
    RefreshTokenStoreStateChanged,
    truncate_or_none,
)


class RedisRefreshTokenStore:
    def __init__(
        self,
        *,
        redis_client: Redis | None = None,
        redis_url: str | None = None,
        key_prefix: str = "my-life-movie",
        retention_seconds: int = 86_400,
    ) -> None:
        if redis_client is None and redis_url is None:
            raise ValueError("Redis client 또는 redis_url이 필요합니다.")

        self.redis = redis_client or Redis.from_url(redis_url, decode_responses=True)
        self.key_prefix = key_prefix.strip(":")
        self.retention_seconds = retention_seconds

    def create(
        self,
        *,
        user_id: int,
        token_hash: str,
        token_family_id: str,
        expires_at: datetime,
        metadata: RefreshTokenMetadata,
        previous_token_id: int | None = None,
    ) -> AuthRefreshToken:
        token = self._build_token(
            token_id=self._next_id(),
            user_id=user_id,
            token_hash=token_hash,
            token_family_id=token_family_id,
            expires_at=expires_at,
            metadata=metadata,
            previous_token_id=previous_token_id,
        )
        self._save_token(token)
        return token

    def get_by_hash(self, token_hash: str) -> AuthRefreshToken | None:
        token_id = self.redis.get(self._hash_key(token_hash))
        if token_id is None:
            return None

        payload = self.redis.get(self._token_key(int(token_id)))
        if payload is None:
            return None

        return deserialize_token(payload)

    def get_active_by_hash(self, token_hash: str) -> AuthRefreshToken | None:
        token = self.get_by_hash(token_hash)
        if token is None or token.status != RefreshTokenStatus.ACTIVE:
            return None

        return token

    def rotate(
        self,
        *,
        current_token: AuthRefreshToken,
        new_token_hash: str,
        expires_at: datetime,
        metadata: RefreshTokenMetadata,
    ) -> AuthRefreshToken:
        if current_token.id is None:
            raise ValueError("저장된 refresh token만 회전할 수 있습니다.")

        current_key = self._token_key(current_token.id)
        for _ in range(3):
            try:
                with self.redis.pipeline() as pipeline:
                    pipeline.watch(current_key)
                    latest_token = self._load_watched_token(
                        pipeline,
                        current_key,
                        current_token,
                    )
                    new_token = self._build_token(
                        token_id=self._next_id(),
                        user_id=latest_token.user_id,
                        token_hash=new_token_hash,
                        token_family_id=latest_token.token_family_id,
                        expires_at=expires_at,
                        metadata=metadata,
                        previous_token_id=latest_token.id,
                    )

                    now = now_utc()
                    latest_token.status = RefreshTokenStatus.ROTATED
                    latest_token.last_used_at = now
                    latest_token.replaced_by_token_id = new_token.id
                    latest_token.updated_at = now

                    pipeline.multi()
                    self._queue_save_token(pipeline, latest_token)
                    self._queue_save_token(pipeline, new_token)
                    pipeline.execute()
                    copy_token_state(source=latest_token, target=current_token)
                    return new_token
            except WatchError:
                continue

        raise RefreshTokenStoreStateChanged("refresh token 상태가 변경되었습니다.")

    def revoke(
        self,
        *,
        current_token: AuthRefreshToken,
        reason: str,
    ) -> AuthRefreshToken:
        if current_token.id is None:
            raise ValueError("저장된 refresh token만 폐기할 수 있습니다.")

        current_key = self._token_key(current_token.id)
        for _ in range(3):
            try:
                with self.redis.pipeline() as pipeline:
                    pipeline.watch(current_key)
                    latest_token = self._load_watched_token(
                        pipeline,
                        current_key,
                        current_token,
                    )

                    now = now_utc()
                    latest_token.status = RefreshTokenStatus.REVOKED
                    latest_token.revoked_at = now
                    latest_token.revoked_reason = truncate_or_none(reason, 120)
                    latest_token.updated_at = now

                    pipeline.multi()
                    self._queue_save_token(pipeline, latest_token)
                    pipeline.execute()
                    copy_token_state(source=latest_token, target=current_token)
                    return current_token
            except WatchError:
                continue

        raise RefreshTokenStoreStateChanged("refresh token 상태가 변경되었습니다.")

    def mark_expired(self, current_token: AuthRefreshToken) -> AuthRefreshToken:
        current_token.status = RefreshTokenStatus.EXPIRED
        current_token.updated_at = now_utc()
        self._save_token(current_token)
        return current_token

    def _load_watched_token(
        self,
        pipeline,
        current_key: str,
        expected_token: AuthRefreshToken,
    ) -> AuthRefreshToken:
        payload = pipeline.get(current_key)
        if payload is None:
            pipeline.unwatch()
            raise RefreshTokenStoreStateChanged("refresh token을 찾을 수 없습니다.")

        latest_token = deserialize_token(payload)
        if (
            latest_token.id != expected_token.id
            or latest_token.token_hash != expected_token.token_hash
            or latest_token.status != RefreshTokenStatus.ACTIVE
        ):
            pipeline.unwatch()
            raise RefreshTokenStoreStateChanged("refresh token 상태가 변경되었습니다.")

        return latest_token

    def _build_token(
        self,
        *,
        token_id: int,
        user_id: int,
        token_hash: str,
        token_family_id: str,
        expires_at: datetime,
        metadata: RefreshTokenMetadata,
        previous_token_id: int | None = None,
    ) -> AuthRefreshToken:
        now = now_utc()
        return AuthRefreshToken(
            id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            token_family_id=token_family_id,
            previous_token_id=previous_token_id,
            status=RefreshTokenStatus.ACTIVE,
            expires_at=as_utc(expires_at),
            user_agent=truncate_or_none(metadata.user_agent, 255),
            ip_address=truncate_or_none(metadata.ip_address, 45),
            created_at=now,
            updated_at=now,
        )

    def _next_id(self) -> int:
        return int(self.redis.incr(self._id_key()))

    def _save_token(self, token: AuthRefreshToken) -> None:
        if token.id is None:
            raise ValueError("저장할 refresh token id가 필요합니다.")

        with self.redis.pipeline() as pipeline:
            self._queue_save_token(pipeline, token)
            pipeline.execute()

    def _queue_save_token(self, pipeline, token: AuthRefreshToken) -> None:
        if token.id is None:
            raise ValueError("저장할 refresh token id가 필요합니다.")

        ttl_seconds = token_ttl_seconds(token.expires_at, self.retention_seconds)
        pipeline.set(
            self._token_key(token.id),
            serialize_token(token),
            ex=ttl_seconds,
        )
        pipeline.set(
            self._hash_key(token.token_hash),
            str(token.id),
            ex=ttl_seconds,
        )

    def _id_key(self) -> str:
        return f"{self.key_prefix}:auth_refresh_tokens:id_seq"

    def _token_key(self, token_id: int) -> str:
        return f"{self.key_prefix}:auth_refresh_tokens:token:{token_id}"

    def _hash_key(self, token_hash: str) -> str:
        return f"{self.key_prefix}:auth_refresh_tokens:hash:{token_hash}"


def serialize_token(token: AuthRefreshToken) -> str:
    payload = {
        "id": token.id,
        "user_id": token.user_id,
        "token_hash": token.token_hash,
        "token_family_id": token.token_family_id,
        "previous_token_id": token.previous_token_id,
        "replaced_by_token_id": token.replaced_by_token_id,
        "status": token_status_value(token.status),
        "expires_at": datetime_to_iso(token.expires_at),
        "last_used_at": datetime_to_iso(token.last_used_at),
        "revoked_at": datetime_to_iso(token.revoked_at),
        "revoked_reason": token.revoked_reason,
        "user_agent": token.user_agent,
        "ip_address": token.ip_address,
        "created_at": datetime_to_iso(token.created_at),
        "updated_at": datetime_to_iso(token.updated_at),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def deserialize_token(payload: str) -> AuthRefreshToken:
    data: dict[str, Any] = json.loads(payload)
    return AuthRefreshToken(
        id=int(data["id"]),
        user_id=int(data["user_id"]),
        token_hash=data["token_hash"],
        token_family_id=data["token_family_id"],
        previous_token_id=optional_int(data.get("previous_token_id")),
        replaced_by_token_id=optional_int(data.get("replaced_by_token_id")),
        status=RefreshTokenStatus(data["status"]),
        expires_at=parse_datetime(data["expires_at"]),
        last_used_at=parse_optional_datetime(data.get("last_used_at")),
        revoked_at=parse_optional_datetime(data.get("revoked_at")),
        revoked_reason=data.get("revoked_reason"),
        user_agent=data.get("user_agent"),
        ip_address=data.get("ip_address"),
        created_at=parse_datetime(data["created_at"]),
        updated_at=parse_datetime(data["updated_at"]),
    )


def token_ttl_seconds(expires_at: datetime, retention_seconds: int) -> int:
    remaining_seconds = int((as_utc(expires_at) - now_utc()).total_seconds())
    return max(1, remaining_seconds + max(0, retention_seconds))


def token_status_value(status: RefreshTokenStatus | str) -> str:
    if isinstance(status, RefreshTokenStatus):
        return status.value

    return str(status)


def datetime_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None

    return as_utc(value).isoformat()


def parse_datetime(value: str) -> datetime:
    return as_utc(datetime.fromisoformat(value))


def parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None

    return parse_datetime(value)


def optional_int(value: int | str | None) -> int | None:
    if value is None:
        return None

    return int(value)


def copy_token_state(*, source: AuthRefreshToken, target: AuthRefreshToken) -> None:
    target.status = source.status
    target.last_used_at = source.last_used_at
    target.revoked_at = source.revoked_at
    target.revoked_reason = source.revoked_reason
    target.replaced_by_token_id = source.replaced_by_token_id
    target.updated_at = source.updated_at


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)
