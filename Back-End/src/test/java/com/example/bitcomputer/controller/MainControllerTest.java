package com.example.bitcomputer.controller;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
class MainControllerTest {

    MockMvc mockMvc;

    @Mock
    DataSource dataSource;

    @Mock
    StringRedisTemplate stringRedisTemplate;

    @InjectMocks
    MainController mainController;

    @BeforeEach
    void setup() {
        mockMvc = MockMvcBuilders.standaloneSetup(mainController).build();
    }

    @Test
    @DisplayName("DB/Redis UP일 때 200 OK 및 상태 필드 포함")
    void health_ok() throws Exception {
        Connection conn = mock(Connection.class);
        DatabaseMetaData meta = mock(DatabaseMetaData.class);
        when(dataSource.getConnection()).thenReturn(conn);
        when(conn.getMetaData()).thenReturn(meta);
        when(meta.getURL()).thenReturn("jdbc:h2:mem");
        when(meta.getUserName()).thenReturn("sa");
        when(conn.getCatalog()).thenReturn("test");

        // Redis mock
        RedisConnectionFactory factory = mock(LettuceConnectionFactory.class);
        when(((LettuceConnectionFactory) factory).getHostName()).thenReturn("localhost");
        when(((LettuceConnectionFactory) factory).getPort()).thenReturn(6379);
        when(stringRedisTemplate.getConnectionFactory()).thenReturn(factory);
        when(stringRedisTemplate.execute(org.mockito.ArgumentMatchers.<org.springframework.data.redis.core.RedisCallback<String>>any()))
                .thenReturn("PONG");

        mockMvc.perform(get("/health/db").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.mysql.status").value("UP"))
                .andExpect(jsonPath("$.redis.status").value("UP"));
    }
}
