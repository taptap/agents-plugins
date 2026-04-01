# Java 单元测试参考模板

Java — JUnit 5 + Mockito

## 参数化测试

```java
@ParameterizedTest
@MethodSource("parseConfigTestCases")
void testParseConfig(String input, Config expected, Class<? extends Exception> expectedException) {
    if (expectedException != null) {
        assertThrows(expectedException, () -> ConfigParser.parse(input));
    } else {
        Config result = ConfigParser.parse(input);
        assertEquals(expected, result);
    }
}

static Stream<Arguments> parseConfigTestCases() {
    return Stream.of(
        Arguments.of("{\"key\": \"value\"}", new Config("value"), null),
        Arguments.of("", null, ParseException.class),
        Arguments.of(null, null, NullPointerException.class)
    );
}
```

## Mock 依赖（Mockito）

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepo;

    @InjectMocks
    private UserService userService;

    @Test
    void shouldGetUserById() {
        when(userRepo.findById(1L)).thenReturn(Optional.of(new User(1L, "Alice")));

        User user = userService.getUser(1L);

        assertEquals("Alice", user.getName());
        verify(userRepo).findById(1L);
    }
}
```
