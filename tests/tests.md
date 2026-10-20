# YubaLANG User Tests

These tests verify core YubaLANG language features from the perspective of someone learning the language for the first time.

---

## Test 1 — Hello World

```hl
text output "Hello, world!"
```

Expected output:

```text
Hello, world!
```

---

## Test 2 — Integer Variable

```hl
define var number: int = 42
text output number
```

Expected output:

```text
42
```

---

## Test 3 — Float Variable

```hl
define var number: float = 3.14
text output number
```

Expected output:

```text
3.14
```

---

## Test 4 — String Variable

```hl
define var message: string = "Hello"
text output message
```

Expected output:

```text
Hello
```

---

## Test 5 — Boolean Variable

```hl
define var enabled: bool = true
text output enabled
```

Expected output:

```text
True
```

---

## Test 6 — Arithmetic

```hl
arith add 10 5
arith sub 10 5
arith mul 10 5
arith div 10 5
arith mod 10 3
```

Expected output:

```text
15
5
50
2.0
1
```

---

## Test 7 — Type Conversion

```hl
define var number: int = 42

convert number to float
text output number

convert number to string
text output number
```

Expected output should show the converted value after each conversion.

---

## Test 8 — Comparisons

```hl
define var result: bool = false

compare 10 > 5 result

text output result
```

Expected output:

```text
True
```

---

## Test 9 — If / Else

```hl
define var result: bool = true

if result
    text output "YES"
else
    text output "NO"
endif
```

Expected output:

```text
YES
```

---

## Test 10 — Function

```hl
func define test
    text output "Function works!"
endfunc

func call test
```

Expected output:

```text
Function works!
```

---

## Test 11 — Return

```hl
func define test
    text output "Before"
    return
    text output "After"
endfunc

func call test
```

Expected output:

```text
Before
```

---

## Test 12 — For Loop

```hl
loop for 3
    text output "Loop"
endloop
```

Expected output:

```text
Loop
Loop
Loop
```

---

## Test 13 — List Append

```hl
define var numbers: list = [1, 2]

list append numbers 3

arith sum numbers
```

Expected output:

```text
6
```

---

## Test 14 — List Get

```hl
define var numbers: list = [10, 20, 30]
define var result: int = 0

list get numbers 1 result

text output result
```

Expected output:

```text
20
```

---

## Test 15 — List Length

```hl
define var numbers: list = [1, 2, 3, 4]
define var length: int = 0

list len numbers length

text output length
```

Expected output:

```text
4
```

---

## Test 16 — List Arithmetic

```hl
define var numbers: list = [5, 10, 15]

arith sum numbers
arith max numbers
arith min numbers
```

Expected output:

```text
30
15
5
```

---

## Test 17 — Input

```hl
define var name: string = ""

text input name
text output name
```

Enter:

```text
YubaLANG
```

Expected output:

```text
YubaLANG
```

---

## Test 18 — Wait

```hl
text output "Before"
wait 1
text output "After"
```

Expected behavior:

`After` should appear approximately one second after `Before`.

---

# Invalid Input Tests

These tests make sure common mistakes produce errors instead of silently succeeding.

## Test 19 — Undefined Variable

```hl
text output does_not_exist
```

Expected: an error stating that the variable is not defined.

---

## Test 20 — Invalid Type

```hl
define var number: banana = 5
```

Expected: an unknown-type error.

---

## Test 21 — Division by Zero

```hl
arith div 10 0
```

Expected: a divide-by-zero error.

---

## Test 22 — Invalid List Index

```hl
define var numbers: list = [1, 2]
define var result: int = 0

list get numbers 10 result
```

Expected: a list index error.

---

## Test 23 — Unknown Command

```hl
something totally_invalid
```

Expected: an unknown-command error.

---

# New User Acceptance Criteria

YubaLANG passes the new-user test set when:

* Basic programs execute successfully.
* Variables work for all supported types.
* Type conversion works.
* Arithmetic works.
* Comparisons work.
* Conditional blocks work.
* Functions can be defined and called.
* `return` works.
* Loops work.
* Lists work.
* Input and output work.
* `wait` works.
* Invalid programs produce understandable runtime errors.