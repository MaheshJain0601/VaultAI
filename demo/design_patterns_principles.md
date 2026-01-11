# Design Patterns & Principles

## What Are Design Patterns?

Design patterns are reusable solutions to commonly occurring problems in software design. They represent best practices evolved over time by experienced developers. Patterns are not finished designs that can be directly transformed into code—they are templates describing how to solve problems that can be adapted to many different situations.

## Why Use Design Patterns?

- **Proven Solutions**: Patterns have been refined over years of real-world usage
- **Common Vocabulary**: Developers can communicate complex ideas quickly using pattern names
- **Avoid Reinventing the Wheel**: Leverage solutions that have already been tested and optimized
- **Maintainability**: Code structured around patterns is easier to understand and modify
- **Scalability**: Patterns help build systems that can grow and evolve

---

## Categories of Design Patterns

### 1. Creational Patterns

Focus on object creation mechanisms, trying to create objects in a manner suitable to the situation.

| Pattern | Purpose |
|---------|---------|
| **Singleton** | Ensures a class has only one instance with a global access point |
| **Factory Method** | Creates objects without specifying the exact class to create |
| **Abstract Factory** | Creates families of related objects without specifying concrete classes |
| **Builder** | Constructs complex objects step by step |
| **Prototype** | Creates new objects by cloning existing ones |

### 2. Structural Patterns

Deal with object composition—how classes and objects are composed to form larger structures.

| Pattern | Purpose |
|---------|---------|
| **Adapter** | Allows incompatible interfaces to work together |
| **Bridge** | Separates abstraction from implementation |
| **Composite** | Composes objects into tree structures |
| **Decorator** | Adds behavior to objects dynamically |
| **Facade** | Provides a simplified interface to a complex subsystem |
| **Flyweight** | Shares common state between multiple objects efficiently |
| **Proxy** | Provides a surrogate or placeholder for another object |

### 3. Behavioral Patterns

Concerned with algorithms and the assignment of responsibilities between objects.

| Pattern | Purpose |
|---------|---------|
| **Chain of Responsibility** | Passes requests along a chain of handlers |
| **Command** | Encapsulates a request as an object |
| **Iterator** | Accesses elements of a collection sequentially |
| **Mediator** | Reduces chaotic dependencies between objects |
| **Memento** | Saves and restores previous state of an object |
| **Observer** | Notifies multiple objects about state changes |
| **State** | Alters behavior when internal state changes |
| **Strategy** | Defines a family of interchangeable algorithms |
| **Template Method** | Defines the skeleton of an algorithm in a base class |
| **Visitor** | Separates algorithms from the objects they operate on |

---

## SOLID Principles

SOLID is an acronym for five design principles that make software designs more understandable, flexible, and maintainable.

### S - Single Responsibility Principle (SRP)

> A class should have only one reason to change.

**Why It Matters:**
- Reduces complexity by limiting what each class does
- Makes code easier to test and debug
- Changes in one area don't ripple through unrelated code

### O - Open/Closed Principle (OCP)

> Software entities should be open for extension but closed for modification.

**Why It Matters:**
- Add new features without changing existing code
- Reduces risk of breaking working functionality
- Promotes use of abstractions and polymorphism

### L - Liskov Substitution Principle (LSP)

> Objects of a superclass should be replaceable with objects of its subclasses without affecting program correctness.

**Why It Matters:**
- Ensures inheritance hierarchies are properly designed
- Prevents unexpected behavior when using polymorphism
- Strengthens the reliability of abstractions

### I - Interface Segregation Principle (ISP)

> Clients should not be forced to depend on interfaces they do not use.

**Why It Matters:**
- Prevents "fat" interfaces that do too much
- Reduces coupling between modules
- Makes implementations more focused and maintainable

### D - Dependency Inversion Principle (DIP)

> High-level modules should not depend on low-level modules. Both should depend on abstractions.

**Why It Matters:**
- Decouples components for easier testing and swapping
- Enables dependency injection
- Makes systems more modular and flexible

---

## Other Important Principles

### DRY (Don't Repeat Yourself)

Every piece of knowledge should have a single, unambiguous representation in the system.

**Benefits:**
- Reduces maintenance burden
- Single source of truth for logic
- Easier refactoring

### KISS (Keep It Simple, Stupid)

Simplicity should be a key goal in design; unnecessary complexity should be avoided.

**Benefits:**
- Easier to understand and debug
- Faster development
- Lower cognitive load for team members

### YAGNI (You Aren't Gonna Need It)

Don't implement functionality until it's actually needed.

**Benefits:**
- Avoids wasted effort on unused features
- Keeps codebase lean
- Reduces technical debt from speculative features

### Composition Over Inheritance

Favor object composition over class inheritance for code reuse.

**Benefits:**
- More flexible runtime behavior changes
- Avoids fragile base class problems
- Looser coupling between components

### Separation of Concerns

Different aspects of a program should be managed by distinct sections with minimal overlap.

**Benefits:**
- Independent development and testing
- Easier to modify one aspect without affecting others
- Better code organization

---

## When to Apply Patterns

| Situation | Recommendation |
|-----------|----------------|
| Code smells or growing complexity | Refactor using appropriate patterns |
| Building new systems | Design with patterns where they naturally fit |
| Adding new features | Consider patterns to maintain extensibility |
| Performance bottlenecks | Use structural patterns like Flyweight or Proxy |

## Common Anti-Patterns to Avoid

- **God Object**: A class that knows or does too much
- **Spaghetti Code**: Unstructured, tangled control flow
- **Golden Hammer**: Overusing a familiar pattern for every problem
- **Premature Optimization**: Optimizing before understanding actual bottlenecks
- **Copy-Paste Programming**: Duplicating code instead of abstracting

---

## Key Takeaways

1. Design patterns are tools, not rules—apply them where they provide clear value
2. SOLID principles guide day-to-day coding decisions
3. Patterns improve communication among developers
4. Start simple; introduce patterns as complexity demands
5. Understanding *why* a pattern exists is more important than memorizing its structure

