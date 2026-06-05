package com.example.bitcomputer.controller;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.util.HashMap;
import java.util.Map;

@RestController
@Slf4j
@Controller
public class MainController {
    @Autowired
    private DataSource dataSource;
    @Autowired
    private StringRedisTemplate redisTemplate;

    @GetMapping("/health/db")
    public ResponseEntity<Map<String, Object>> checkDatabaseConnections() {
        Map<String, Object> status = new HashMap<>();
        
        // MySQL 연결 확인
        try (Connection conn = dataSource.getConnection()) {
            DatabaseMetaData metaData = conn.getMetaData();
            status.put("mysql", Map.of(
                "status", "UP",
                "url", metaData.getURL(),
                "database", conn.getCatalog(),
                "user", metaData.getUserName()
            ));
        } catch (Exception e) {
            log.error("MySQL connection error", e);
            status.put("mysql", Map.of(
                "status", "DOWN",
                "error", e.getMessage()
            ));
        }
        
        // Redis 연결 확인
        try {
            String result = redisTemplate.execute(RedisConnection::ping);
            RedisConnectionFactory factory = redisTemplate.getConnectionFactory();
            LettuceConnectionFactory lettuce = (LettuceConnectionFactory) factory;
            
            status.put("redis", Map.of(
                "status", "UP",
                "host", lettuce.getHostName(),
                "port", lettuce.getPort(),
                "ping", result
            ));
        } catch (Exception e) {
            log.error("Redis connection error", e);
            status.put("redis", Map.of(
                "status", "DOWN",
                "error", e.getMessage()
            ));
        }
        
        return ResponseEntity.ok(status);
    }

}
