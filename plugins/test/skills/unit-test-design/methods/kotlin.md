# Kotlin 单元测试参考模板

Kotlin — JUnit 5 + MockK

## Mock 依赖（MockK）

```kotlin
class UserServiceTest {

    private val userRepo = mockk<UserRepository>()
    private val svc = UserService(userRepo)

    @Test
    fun `should get user by id`() {
        every { userRepo.findById(1L) } returns User(1L, "Alice")

        val user = svc.getUser(1L)

        assertEquals("Alice", user.name)
        verify { userRepo.findById(1L) }
    }
}
```
