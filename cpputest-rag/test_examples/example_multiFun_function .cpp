// Example CppUTest file – multiple embedded-style functions
#include "CppUTest/TestHarness.h"
#include <string.h>
#include <ctype.h>

/* ============================================================
 * Function 1: String Reverse
 * ============================================================ */

// Function under test
char* string_reverse(char* str)
{
    if (!str) return NULL;

    int len = strlen(str);
    for (int i = 0; i < len / 2; i++)
    {
        char temp = str[i];
        str[i] = str[len - 1 - i];
        str[len - 1 - i] = temp;
    }

    return str;
}

TEST_GROUP(StringReverse)
{
    char buffer[100];

    void setup()
    {
        memset(buffer, 0, sizeof(buffer));
    }

    void teardown()
    {
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

/* ============================================================
 * Function 2: String To Upper
 * ============================================================ */

// Function under test
char* string_to_upper(char* str)
{
    if (!str) return NULL;

    for (int i = 0; str[i] != '\0'; i++)
    {
        str[i] = (char)toupper((unsigned char)str[i]);
    }

    return str;
}

TEST_GROUP(StringToUpper)
{
    char buffer[100];

    void setup()
    {
        memset(buffer, 0, sizeof(buffer));
    }

    void teardown()
    {
    }
};

TEST(StringToUpper, ConvertNormalString)
{
    strcpy(buffer, "hello");
    string_to_upper(buffer);
    STRCMP_EQUAL("HELLO", buffer);
}

TEST(StringToUpper, ConvertMixedCase)
{
    strcpy(buffer, "HeLLo");
    string_to_upper(buffer);
    STRCMP_EQUAL("HELLO", buffer);
}

TEST(StringToUpper, ConvertEmptyString)
{
    strcpy(buffer, "");
    string_to_upper(buffer);
    STRCMP_EQUAL("", buffer);
}

TEST(StringToUpper, ConvertNullPointer)
{
    char* result = string_to_upper(NULL);
    CHECK(result == NULL);
}

/* ============================================================
 * Function 3: Clamp Integer
 * ============================================================ */

// Function under test
int clamp_int(int value, int min, int max)
{
    if (value < min) return min;
    if (value > max) return max;
    return value;
}

TEST_GROUP(ClampInt)
{
    void setup()
    {
    }

    void teardown()
    {
    }
};

TEST(ClampInt, ValueInsideRange)
{
    LONGS_EQUAL(5, clamp_int(5, 0, 10));
}

TEST(ClampInt, ValueBelowRange)
{
    LONGS_EQUAL(0, clamp_int(-5, 0, 10));
}

TEST(ClampInt, ValueAboveRange)
{
    LONGS_EQUAL(10, clamp_int(20, 0, 10));
}

/* ============================================================
 * Function 4: Array Sum
 * ============================================================ */

// Function under test
int array_sum(const int* arr, int length)
{
    if (!arr || length <= 0) return 0;

    int sum = 0;
    for (int i = 0; i < length; i++)
    {
        sum += arr[i];
    }

    return sum;
}

TEST_GROUP(ArraySum)
{
    int data[5];

    void setup()
    {
        memset(data, 0, sizeof(data));
    }

    void teardown()
    {
    }
};

TEST(ArraySum, NormalArray)
{
    int values[] = {1, 2, 3};
    LONGS_EQUAL(6, array_sum(values, 3));
}

TEST(ArraySum, SingleElement)
{
    int values[] = {5};
    LONGS_EQUAL(5, array_sum(values, 1));
}

TEST(ArraySum, NullPointer)
{
    LONGS_EQUAL(0, array_sum(NULL, 5));
}

/* ============================================================
 * Function 5: Bit Check
 * ============================================================ */

// Function under test
int is_bit_set(unsigned int value, unsigned int bit)
{
    if (bit >= 32) return 0;
    return (value & (1U << bit)) != 0U;
}

TEST_GROUP(BitCheck)
{
    void setup()
    {
    }

    void teardown()
    {
    }
};

TEST(BitCheck, BitIsSet)
{
    CHECK_TRUE(is_bit_set(0x04U, 2));
}

TEST(BitCheck, BitIsNotSet)
{
    CHECK_FALSE(is_bit_set(0x04U, 1));
}

TEST(BitCheck, InvalidBit)
{
    CHECK_FALSE(is_bit_set(0x01U, 32));
}

/* ============================================================
 * Function 6: Simple Counter (Stateful)
 * ============================================================ */

// Function under test
static int counter = 0;

void counter_reset(void)
{
    counter = 0;
}

int counter_increment(void)
{
    return ++counter;
}

TEST_GROUP(Counter)
{
    void setup()
    {
        counter_reset();
    }

    void teardown()
    {
    }
};

TEST(Counter, IncrementOnce)
{
    LONGS_EQUAL(1, counter_increment());
}

TEST(Counter, IncrementTwice)
{
    counter_increment();
    LONGS_EQUAL(2, counter_increment());
}
