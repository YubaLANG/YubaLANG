# YubaLANG Example Programs

## hello.yl

```hl
text output "Hello, world!"
```

---

## variables.yl

```hl
define var name: string = "YubaLANG"
define var version: float = 1.0
define var active: bool = true

text output name
text output version
text output active
```

---

## calculator.yl

```hl
define var a: int = 20
define var b: int = 5

arith add a b
arith sub a b
arith mul a b
arith div a b
arith mod a b
```

---

## lists.yl

```hl
define var numbers: list = [10, 20, 30]

list append numbers 40

define var item: int = 0
list get numbers 2 item

text output item

define var length: int = 0
list len numbers length

text output length

arith sum numbers
arith max numbers
arith min numbers
```

---

## conditions.yl

```hl
define var score: int = 75
define var passing: bool = false

compare score >= 60 passing

if passing
    text output "Passing"
else
    text output "Not passing"
endif
```

---

## functions.yl

```hl
func define greet
    text output "Hello from YubaLANG!"
endfunc

func call greet
```

---

## loops.yl

```hl
loop for 5
    text output "Loop iteration"
endloop
```

---

## input.yl

```hl
define var name: string = ""

text output "Enter your name:"
text input name

text output name
```

---

## conversion.yl

```hl
define var number: int = 42

convert number to float
text output number

convert number to string
text output number
```

---

## complete.yl

```hl
define var language: string = "YubaLANG"
define var numbers: list = [10, 20, 30]

text output "Language:"
text output language

text output "Numbers:"
arith sum numbers

define var largest: int = 0
list get numbers 2 largest

define var is_large: bool = false
compare largest > 20 is_large

if is_large
    text output "The largest number is greater than 20."
else
    text output "The largest number is not greater than 20."
endif

func define finish
    text output "Program finished."
endfunc

func call finish
```