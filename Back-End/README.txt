
SpringBoot : 3.5.6
build: Gradle-Groovy
JDK: JDK 23.0.1
Java: 23
Packaging: Jar

가상환경 설정 불필요
JVM이 있어서 어떤 운영체제든 상관 없이 동일하게 작동해요
Gradle로 필요한 implementation 버전에 맞춰 명시해주면 나중에 알아서 빌드해줍니다

윈도우 빌드 명령어 : ./gradlew clean build
윈도우 스프링부트 실행 명령어 : gradlew.bat bootRun
맥 스프링부트 실행 명령어 : ./gradlew bootRun
(인텔리제이 사용하시면 더 편할지도..)

의존성 목록(build.gradle에 dependencies 에 기재되어있고, 빌드하실 때 해당 패키지가 설치된다고 생각하시면 편합니다. 당연히 우리끼리 통일해놔야해용)
dependencies {
    implementation 'org.springframework.modulith:spring-modulith-starter-core'
    implementation 'com.graphql-java:java-dataloader:3.3.0'
    compileOnly 'org.projectlombok:lombok'
    developmentOnly 'org.springframework.boot:spring-boot-devtools'
    developmentOnly 'org.springframework.boot:spring-boot-docker-compose'
    annotationProcessor 'org.springframework.boot:spring-boot-configuration-processor'
    annotationProcessor 'org.projectlombok:lombok'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.springframework.modulith:spring-modulith-starter-test'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}