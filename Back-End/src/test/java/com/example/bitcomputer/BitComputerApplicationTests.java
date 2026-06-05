package com.example.bitcomputer;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
@Disabled("Skip context load during unit tests to avoid external infra dependencies")
class BitComputerApplicationTests {

    @Test
    void contextLoads() {
    }

}
