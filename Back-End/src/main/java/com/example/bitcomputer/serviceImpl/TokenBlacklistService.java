package com.example.bitcomputer.serviceImpl;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import java.util.Set;
import java.util.concurrent.TimeUnit;

@Service
public class TokenBlacklistService {

    private final RedisTemplate<String, Object> redisTemplate;
    private static final String BLACKLIST_PREFIX = "blacklist:";

    public TokenBlacklistService(RedisTemplate<String, Object> redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public void blacklistToken(String token, long expirationTimeInSeconds) {
        redisTemplate.opsForValue().set(BLACKLIST_PREFIX + token, "blacklisted", expirationTimeInSeconds, TimeUnit.SECONDS);
    }

    public boolean isBlacklisted(String token) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(BLACKLIST_PREFIX + token));
    }

    public void clearBlacklist() {
        Set<String> keys = redisTemplate.keys(BLACKLIST_PREFIX + "*");
        if (keys != null && !keys.isEmpty()) {
            redisTemplate.delete(keys);
        }
    }
}

