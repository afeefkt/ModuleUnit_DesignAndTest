// Example CppUTest for string manipulation
#include "CppUTest/TestHarness.h"
#include <string.h>

// Function under test
char* string_reverse(char* str) {
    if (!str) return NULL;
    int len = strlen(str);
    for (int i = 0; i < len/2; i++) {
        char temp = str[i];
        str[i] = str[len-1-i];
        str[len-1-i] = temp;
    }
    return str;
}

TEST_GROUP(StringReverse)
{
    char buffer[100];
    
    void setup() {
        memset(buffer, 0, sizeof(buffer));
    }
    
    void teardown() {
    }
};

TEST(StringReverse, ReverseNormalString)
{
    strcpy(buffer, "hello");
    string_reverse(buffer);
    STRCMP_EQUAL("olleh", buffer);
}

TEST(StringReverse, ReverseSingleCharacter)
{
    strcpy(buffer, "a");
    string_reverse(buffer);
    STRCMP_EQUAL("a", buffer);
}

TEST(StringReverse, ReverseEmptyString)
{
    strcpy(buffer, "");
    string_reverse(buffer);
    STRCMP_EQUAL("", buffer);
}

TEST(StringReverse, ReverseNullPointer)
{
    char* result = string_reverse(NULL);
    CHECK(result == NULL);
}
