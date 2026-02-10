"""Create default CppUTest example files for RAG training"""

import logging

from app.config import config

logger = logging.getLogger(__name__)


def create_example_cpputest_files():
    """Create example CppUTest files if they don't already exist"""
    examples_dir = config.TEST_EXAMPLES_DIR

    example1 = examples_dir / "example_simple_function.cpp"
    if not example1.exists():
        with open(example1, 'w') as f:
            f.write("""// Example CppUTest for a simple function
#include "CppUTest/TestHarness.h"

// Function under test
int add(int a, int b) {
    return a + b;
}

TEST_GROUP(AddFunctionTests)
{
    void setup() {
        // Setup before each test
    }

    void teardown() {
        // Cleanup after each test
    }
};

TEST(AddFunctionTests, AddPositiveNumbers)
{
    // Test adding two positive numbers
    int result = add(5, 3);
    CHECK_EQUAL(8, result);
}

TEST(AddFunctionTests, AddNegativeNumbers)
{
    // Test adding two negative numbers
    int result = add(-5, -3);
    CHECK_EQUAL(-8, result);
}

TEST(AddFunctionTests, AddZero)
{
    // Test adding zero
    int result = add(0, 5);
    CHECK_EQUAL(5, result);
}

TEST(AddFunctionTests, AddMixedSignNumbers)
{
    // Test adding positive and negative
    int result = add(10, -5);
    CHECK_EQUAL(5, result);
}
""")
        logger.info(f"Created example: {example1}")

    example2 = examples_dir / "example_string_function.cpp"
    if not example2.exists():
        with open(example2, 'w') as f:
            f.write("""// Example CppUTest for string manipulation
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
""")
        logger.info(f"Created example: {example2}")
