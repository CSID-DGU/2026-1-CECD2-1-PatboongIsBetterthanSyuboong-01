package com.example.bitcomputer.jwt;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import java.security.Key;
import java.util.Date;

@Component
public class JwtTokenProvider {

    @Value("${jwt.secret}")
    private String secretKey;

    private Key SECRET_KEY;

    private static final long ACCESS_TOKEN_EXPIRATION = 9000000; // 150분
    private static final long REFRESH_TOKEN_EXPIRATION = 604800000; // 7일

    @PostConstruct
    public void init() {
        this.SECRET_KEY = Keys.hmacShaKeyFor(secretKey.getBytes());
    }

    // 액세스 토큰 생성 (권한 포함)
    public String generateAccessToken(String username) {
        if (SECRET_KEY == null) {
            throw new IllegalStateException("SECRET_KEY is not initialized. Check jwt.secret configuration.");
        }
        try {
            return Jwts.builder()
                    .setSubject(username)
                    .setIssuedAt(new Date())
                    .setExpiration(new Date(System.currentTimeMillis() + ACCESS_TOKEN_EXPIRATION))
                    .signWith(SECRET_KEY, SignatureAlgorithm.HS512)
                    .compact();
        } catch (Exception e) {
            throw new RuntimeException("Error generating access token: " + e.getMessage(), e);
        }
    }

    // 리프레시 토큰 생성
    public String generateRefreshToken(String username) {
        if (SECRET_KEY == null) {
            throw new IllegalStateException("SECRET_KEY is not initialized. Check jwt.secret configuration.");
        }
        try {
            return Jwts.builder()
                    .setSubject(username)
                    .setIssuedAt(new Date())
                    .setExpiration(new Date(System.currentTimeMillis() + REFRESH_TOKEN_EXPIRATION))
                    .signWith(SECRET_KEY, SignatureAlgorithm.HS512)
                    .compact();
        } catch (Exception e) {
            throw new RuntimeException("Error generating refresh token: " + e.getMessage(), e);
        }
    }

    // 토큰 유효성 검증
    public boolean validateToken(String token) {
        if (SECRET_KEY == null || token == null || token.isEmpty()) {
            return false;
        }
        try {
            Jwts.parserBuilder().setSigningKey(SECRET_KEY).build().parseClaimsJws(token);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // 사용자 이름 추출
    public String extractUsername(String token) {
        if (SECRET_KEY == null) {
            throw new IllegalStateException("SECRET_KEY is not initialized. Check jwt.secret configuration.");
        }
        try {
            return Jwts.parserBuilder()
                    .setSigningKey(SECRET_KEY)
                    .build()
                    .parseClaimsJws(token)
                    .getBody()
                    .getSubject();
        } catch (Exception e) {
            throw new RuntimeException("Error extracting username from token: " + e.getMessage(), e);
        }
    }

    //토큰의 만료 시간 반환 (밀리초 단위)
    public long getExpiration(String token) {
        if (SECRET_KEY == null) {
            throw new IllegalStateException("SECRET_KEY is not initialized. Check jwt.secret configuration.");
        }
        try {
            return Jwts.parserBuilder()
                    .setSigningKey(SECRET_KEY)
                    .build()
                    .parseClaimsJws(token)
                    .getBody()
                    .getExpiration()
                    .getTime();
        } catch (Exception e) {
            throw new RuntimeException("Error getting expiration from token: " + e.getMessage(), e);
        }
    }

}
