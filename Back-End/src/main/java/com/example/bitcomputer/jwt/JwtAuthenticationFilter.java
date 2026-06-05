package com.example.bitcomputer.jwt;
import com.example.bitcomputer.serviceImpl.TokenBlacklistService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.ArrayList;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenProvider jwtTokenProvider;
    private final TokenBlacklistService tokenBlacklistService;

    public JwtAuthenticationFilter(JwtTokenProvider jwtTokenProvider, TokenBlacklistService tokenBlacklistService) {
        this.jwtTokenProvider = jwtTokenProvider;
        this.tokenBlacklistService = tokenBlacklistService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        String authHeader = request.getHeader("Authorization");
        String path = request.getRequestURI();
        // 개발용: 인증이 필요 없는 경로들
        // if (path.startsWith("/api/user/login") || path.startsWith("/api/user/register")) {
        if (path.startsWith("/api/user/login") ||
            path.startsWith("/api/user/register") ||
            path.startsWith("/api/patients/") ||
            path.startsWith("/api/waiting/") ||
            path.startsWith("/api/diseases") ||
            path.startsWith("/api/diagnoses") ||
            path.startsWith("/api/histories") ||
            path.startsWith("/actuator/") ||
            path.startsWith("/api/radiology/") ||
            path.startsWith("/images/") ||
            path.startsWith("/api/ai/") ||
            path.startsWith("/api/agent/")
        ) {
            filterChain.doFilter(request, response);
            return;
        }

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return;
        }

        String token = authHeader.substring(7);

        if (!jwtTokenProvider.validateToken(token)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.getWriter().write("Invalid token");
            return;
        }

        if (tokenBlacklistService.isBlacklisted(token)) {
            response.setStatus(HttpServletResponse.SC_FORBIDDEN); // 403 상태 반환
            response.getWriter().write("Token has been blacklisted");
            return;
        }

        String username = jwtTokenProvider.extractUsername(token);
        UserDetails userDetails = User.withUsername(username)
                .password("")
                .authorities(new ArrayList<>())
                .build();

        UsernamePasswordAuthenticationToken authentication =
                new UsernamePasswordAuthenticationToken(userDetails, null, userDetails.getAuthorities());
        SecurityContextHolder.getContext().setAuthentication(authentication);

        filterChain.doFilter(request, response);
    }
}
