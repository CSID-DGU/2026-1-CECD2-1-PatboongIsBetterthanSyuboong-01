package com.example.bitcomputer.config;

import com.arangodb.ArangoDB;
import com.arangodb.springframework.annotation.EnableArangoRepositories;
import com.arangodb.springframework.config.ArangoConfiguration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableArangoRepositories(basePackages = "com.example.bitcomputer.Repository.arango")
public class ArangoConfig implements ArangoConfiguration {
    @Value("${arangodb.hosts}")
    private String hosts;

    @Value("${arangodb.user}")
    private String user;

    @Value("${arangodb.password}")
    private String password;

    @Value("${arangodb.database}")
    private String database;

    @Override
    public ArangoDB.Builder arango() {
        String[] hostPort = hosts.split(":");
        return new ArangoDB.Builder()
                .host(hostPort[0], Integer.parseInt(hostPort[1]))
                .user(user)
                .password(password);
    }

    @Override
    public String database() {
        return database;
    }
}
