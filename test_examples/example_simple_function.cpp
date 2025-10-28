// Example CppUTest for a simple function
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
