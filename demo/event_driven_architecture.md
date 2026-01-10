# Event-Driven Architecture and Message Queues

## Introduction

Event-Driven Architecture (EDA) is a software design pattern where the flow of the program is determined by events—significant changes in state or occurrences that the system should react to. This architecture enables loose coupling, scalability, and real-time processing capabilities.

## Core Concepts

### What is an Event?

An event represents something that has happened in the system:

```json
{
  "event_id": "evt_12345",
  "event_type": "order.placed",
  "timestamp": "2026-01-10T14:30:00Z",
  "data": {
    "order_id": "ord_789",
    "customer_id": "cust_456",
    "total_amount": 149.99,
    "items": ["item_1", "item_2"]
  },
  "metadata": {
    "source": "checkout-service",
    "correlation_id": "corr_abc123"
  }
}
```

### Event Types

| Type | Description | Example |
|------|-------------|---------|
| **Domain Events** | Business-significant occurrences | OrderPlaced, PaymentReceived |
| **Integration Events** | Cross-service communication | UserCreated, InventoryUpdated |
| **System Events** | Infrastructure-level events | ServerStarted, ErrorOccurred |

## Architecture Patterns

### 1. Event Notification

Services publish events when something happens; other services react if interested.

```
┌─────────────┐    OrderPlaced    ┌─────────────┐
│   Order     │ ─────────────────►│   Email     │
│   Service   │                   │   Service   │
└─────────────┘                   └─────────────┘
       │
       │         OrderPlaced      ┌─────────────┐
       └─────────────────────────►│  Inventory  │
                                  │   Service   │
                                  └─────────────┘
```

**Characteristics:**
- Fire-and-forget
- Minimal payload (just notification)
- Services query for details if needed

### 2. Event-Carried State Transfer

Events carry all necessary data, reducing need for callbacks.

```json
{
  "event_type": "customer.updated",
  "data": {
    "customer_id": "cust_123",
    "name": "John Doe",
    "email": "john@example.com",
    "shipping_address": {
      "street": "123 Main St",
      "city": "San Francisco",
      "zip": "94102"
    }
  }
}
```

**Benefits:**
- Reduced inter-service queries
- Better autonomy
- Works during source service outages

### 3. Event Sourcing

Store state as a sequence of events rather than current state.

```
Event Store:
┌────────────────────────────────────────────────────┐
│ ID │ Type           │ Data                │ Time   │
├────┼────────────────┼─────────────────────┼────────┤
│ 1  │ AccountOpened  │ {amount: 0}         │ 10:00  │
│ 2  │ MoneyDeposited │ {amount: 100}       │ 10:05  │
│ 3  │ MoneyWithdrawn │ {amount: 30}        │ 10:10  │
│ 4  │ MoneyDeposited │ {amount: 50}        │ 10:15  │
└────────────────────────────────────────────────────┘

Current State: Balance = 0 + 100 - 30 + 50 = $120
```

**Benefits:**
- Complete audit trail
- Temporal queries ("what was state at time X?")
- Event replay for debugging
- Easy to add new projections

### 4. CQRS (Command Query Responsibility Segregation)

Separate read and write models, often combined with Event Sourcing.

```
                    ┌───────────────┐
                    │   Commands    │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Write Model   │
                    │ (Event Store) │
                    └───────┬───────┘
                            │
                      Events│
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
      ┌───────────────┐           ┌───────────────┐
      │ Read Model 1  │           │ Read Model 2  │
      │ (Listings)    │           │ (Analytics)   │
      └───────────────┘           └───────────────┘
              │                           │
              ▼                           ▼
          Queries                     Queries
```

## Message Queue Technologies

### Apache Kafka

**Architecture:**

```
Producers ──► Kafka Cluster ──► Consumers
              (Topics/Partitions)

Topic: orders
┌─────────────────────────────────────────┐
│ Partition 0: [msg1][msg2][msg3][msg4]   │
│ Partition 1: [msg1][msg2][msg3]         │
│ Partition 2: [msg1][msg2][msg3][msg4]   │
└─────────────────────────────────────────┘
```

**Key Features:**
- High throughput (millions of messages/sec)
- Persistent storage (configurable retention)
- Horizontal scaling via partitions
- Consumer groups for parallel processing
- Log compaction for event sourcing

**Use Cases:**
- Real-time analytics
- Log aggregation
- Event sourcing
- Stream processing

### RabbitMQ

**Architecture:**

```
Producer ──► Exchange ──► Queue ──► Consumer
                │
                │ Routing
                ▼
            ┌───────┐
            │ Queue │
            └───────┘
```

**Exchange Types:**
- **Direct**: Route by exact routing key
- **Topic**: Route by pattern matching
- **Fanout**: Broadcast to all queues
- **Headers**: Route by message headers

**Key Features:**
- Multiple protocols (AMQP, MQTT, STOMP)
- Flexible routing
- Message acknowledgment
- Dead letter queues
- Priority queues

**Use Cases:**
- Task queues
- RPC patterns
- Complex routing scenarios

### Amazon SQS

**Types:**
- **Standard Queue**: At-least-once delivery, best-effort ordering
- **FIFO Queue**: Exactly-once, guaranteed ordering

**Key Features:**
- Fully managed
- Automatic scaling
- Dead letter queues
- Long polling
- Server-side encryption

### Comparison

| Feature | Kafka | RabbitMQ | SQS |
|---------|-------|----------|-----|
| Throughput | Very High | High | Medium |
| Ordering | Per partition | Per queue | FIFO only |
| Persistence | Yes (log) | Optional | Yes |
| Replay | Yes | No | No |
| Routing | Basic | Advanced | Basic |
| Managed | Confluent/MSK | CloudAMQP | AWS |

## Design Patterns

### Saga Pattern

Manage distributed transactions through events.

**Choreography Saga:**
```
Order    ──OrderCreated──►  Payment  ──PaymentProcessed──►  Inventory
Service                     Service                         Service
                               │                               │
                               │    PaymentFailed              │
                               └──────────────────────────────►│
                                                    (Compensate)
```

**Orchestration Saga:**
```
                    ┌─────────────────┐
                    │  Saga           │
                    │  Orchestrator   │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌─────────┐        ┌─────────┐        ┌─────────┐
    │ Order   │        │ Payment │        │Inventory│
    │ Service │        │ Service │        │ Service │
    └─────────┘        └─────────┘        └─────────┘
```

### Outbox Pattern

Ensure reliable event publishing with database transactions.

```sql
-- Within same transaction
BEGIN;
  INSERT INTO orders (id, ...) VALUES (...);
  INSERT INTO outbox (event_type, payload) 
    VALUES ('OrderCreated', '{"order_id": "..."}');
COMMIT;

-- Separate process polls outbox and publishes to message queue
```

### Dead Letter Queue

Handle failed messages for analysis and retry.

```
Main Queue ──► Consumer ──► Processing
                  │
                  │ Failed (after N retries)
                  ▼
            Dead Letter Queue ──► Analysis/Manual Review
```

## Best Practices

### Event Design

1. **Make events immutable**: Never modify published events
2. **Include correlation IDs**: Enable request tracing
3. **Version your events**: Handle schema evolution

```json
{
  "event_type": "order.placed",
  "event_version": "2.0",
  "data": { ... }
}
```

4. **Use past tense**: Events describe what happened
5. **Include timestamps**: Enable ordering and debugging

### Error Handling

```python
def process_event(event):
    try:
        handle_event(event)
        acknowledge(event)
    except TemporaryError:
        # Retry with backoff
        retry_with_backoff(event)
    except PermanentError:
        # Send to dead letter queue
        send_to_dlq(event)
        acknowledge(event)
```

### Idempotency

Ensure handlers can process the same event multiple times safely.

```python
def handle_order_placed(event):
    order_id = event['data']['order_id']
    
    # Check if already processed
    if is_processed(order_id):
        return  # Skip duplicate
    
    # Process event
    create_shipment(order_id)
    
    # Mark as processed
    mark_processed(order_id)
```

### Monitoring

Key metrics to track:
- **Lag**: Consumer falling behind producer
- **Throughput**: Messages per second
- **Error rate**: Failed message processing
- **Processing time**: End-to-end latency

## Anti-Patterns to Avoid

### 1. Event Soup
Too many fine-grained events making system hard to understand.

**Bad:**
```
UserFirstNameChanged, UserLastNameChanged, UserEmailChanged
```

**Better:**
```
UserProfileUpdated (with all changed fields)
```

### 2. Event as Command
Using events to tell services what to do (tight coupling).

**Bad:**
```
SendEmailToUser  // This is a command, not an event
```

**Better:**
```
UserRegistered  // Email service decides to send welcome email
```

### 3. Missing Correlation
Unable to trace related events across services.

**Solution:** Always include correlation_id in events.

### 4. Ignoring Event Order

**Problem:** Out-of-order processing causes incorrect state.

**Solutions:**
- Use partitioning (Kafka)
- Sequence numbers
- Causal ordering

## Conclusion

Event-Driven Architecture enables building scalable, loosely-coupled systems that can evolve independently. Key considerations:

1. **Choose the right pattern**: Event notification vs Event Sourcing
2. **Select appropriate technology**: Based on throughput, ordering, and persistence needs
3. **Design events carefully**: Immutable, versioned, with correlation
4. **Handle failures gracefully**: Retries, dead letter queues, idempotency
5. **Monitor extensively**: Lag, throughput, errors

---

*Document Version: 1.0*  
*Category: Architecture Patterns*  
*Last Updated: January 2026*

