# Database Scaling: Sharding, Replication, and Partitioning

## Overview

As applications grow, databases often become the bottleneck. This document covers strategies for scaling databases to handle increased load while maintaining performance and reliability.

## Vertical vs Horizontal Scaling

### Vertical Scaling (Scale Up)
- Add more resources to existing server (CPU, RAM, SSD)
- Simpler to implement
- Has hardware limits
- Single point of failure remains

### Horizontal Scaling (Scale Out)
- Add more database servers
- Theoretically unlimited scaling
- More complex architecture
- Better fault tolerance

## Database Replication

Replication creates copies of data across multiple database servers.

### Master-Slave (Primary-Replica) Replication

```
     Writes
        │
        ▼
   ┌─────────┐
   │ Primary │
   └────┬────┘
        │ Replication
   ┌────┴────┐
   │         │
   ▼         ▼
┌─────┐   ┌─────┐
│Replica│ │Replica│
└─────┘   └─────┘
   │         │
   └────┬────┘
        │
        ▼
      Reads
```

**Characteristics:**
- All writes go to primary
- Reads distributed across replicas
- Replicas are read-only
- Replication can be synchronous or asynchronous

**Pros:**
- Read scalability
- Backup/failover capability
- Geographic distribution

**Cons:**
- Write scalability limited
- Replication lag (eventual consistency)
- Failover complexity

### Master-Master (Multi-Primary) Replication

```
   Writes/Reads          Writes/Reads
        │                      │
        ▼                      ▼
   ┌─────────┐   Sync    ┌─────────┐
   │Primary 1│◄─────────►│Primary 2│
   └─────────┘           └─────────┘
```

**Characteristics:**
- Multiple nodes accept writes
- Bi-directional replication
- Conflict resolution required

**Pros:**
- Write scalability
- No single point of failure
- Low latency for distributed users

**Cons:**
- Conflict handling complexity
- Potential data inconsistency
- More complex setup

## Database Sharding

Sharding horizontally partitions data across multiple database instances.

### Sharding Strategies

#### 1. Range-Based Sharding

Partition data based on value ranges:

```
Shard 1: Users A-H
Shard 2: Users I-P  
Shard 3: Users Q-Z
```

**Pros:**
- Simple to implement
- Range queries efficient within shard

**Cons:**
- Uneven distribution possible (hotspots)
- Rebalancing difficult

#### 2. Hash-Based Sharding

Use hash function to determine shard:

```python
shard_id = hash(user_id) % number_of_shards
```

**Example:**
```
hash("user_123") % 4 = 2  → Shard 2
hash("user_456") % 4 = 0  → Shard 0
hash("user_789") % 4 = 3  → Shard 3
```

**Pros:**
- Even distribution
- Simple routing

**Cons:**
- Range queries across all shards
- Adding shards requires rehashing

#### 3. Directory-Based Sharding

Lookup table maps keys to shards:

```
┌──────────────┬───────────┐
│   Key Range  │   Shard   │
├──────────────┼───────────┤
│  user_1-100  │  Shard 1  │
│  user_101-500│  Shard 2  │
│  user_501+   │  Shard 3  │
└──────────────┴───────────┘
```

**Pros:**
- Flexible assignment
- Easy rebalancing

**Cons:**
- Lookup overhead
- Directory becomes SPOF

#### 4. Geographic Sharding

Partition based on user location:

```
US Shard:     users in North America
EU Shard:     users in Europe
APAC Shard:   users in Asia-Pacific
```

**Pros:**
- Low latency for regional users
- Data sovereignty compliance

**Cons:**
- Cross-region queries slow
- Uneven distribution

### Shard Key Selection

Choosing the right shard key is critical:

**Good Shard Keys:**
- High cardinality (many unique values)
- Even distribution
- Frequently used in queries
- Immutable (or rarely changes)

**Bad Shard Keys:**
- Low cardinality (few values)
- Skewed distribution
- Compound keys that change

**Example Analysis:**

| Shard Key | Cardinality | Distribution | Verdict |
|-----------|-------------|--------------|---------|
| user_id | High | Even | ✅ Good |
| country | Low | Skewed | ❌ Bad |
| created_date | High | Time-skewed | ⚠️ Careful |
| email_hash | High | Even | ✅ Good |

## Partitioning

Partitioning divides a table into smaller pieces within the same database instance.

### Types of Partitioning

#### 1. Horizontal Partitioning
Split rows across partitions:

```sql
-- Orders partitioned by year
CREATE TABLE orders (
    id INT,
    order_date DATE,
    amount DECIMAL
) PARTITION BY RANGE (YEAR(order_date)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026)
);
```

#### 2. Vertical Partitioning
Split columns across tables:

```
users_basic: id, name, email
users_profile: id, bio, avatar, preferences
users_activity: id, last_login, session_count
```

#### 3. List Partitioning
Partition by discrete values:

```sql
CREATE TABLE customers (
    id INT,
    region VARCHAR(20),
    name VARCHAR(100)
) PARTITION BY LIST (region) (
    PARTITION north VALUES IN ('NY', 'MA', 'CT'),
    PARTITION south VALUES IN ('TX', 'FL', 'GA'),
    PARTITION west VALUES IN ('CA', 'WA', 'OR')
);
```

## Handling Cross-Shard Queries

### Challenge
Queries spanning multiple shards require coordination:

```sql
-- This query might span all shards
SELECT * FROM orders WHERE total > 1000 ORDER BY created_at LIMIT 10;
```

### Solutions

#### 1. Scatter-Gather Pattern
```
Query Coordinator
       │
   ┌───┴───┐
   │       │
   ▼       ▼
Shard1  Shard2
   │       │
   └───┬───┘
       │
   Aggregate
```

#### 2. Denormalization
Store redundant data to avoid cross-shard joins:

```
# Instead of joining users and orders tables
# Store user_name directly in orders
orders: id, user_id, user_name, amount
```

#### 3. Application-Level Joins
Fetch from multiple shards and join in application:

```python
user = user_shard.get_user(user_id)
orders = order_shard.get_orders(user_id)
result = join_in_memory(user, orders)
```

## Consistency Models

### Strong Consistency
- All reads see most recent write
- Higher latency
- Use case: Financial transactions

### Eventual Consistency
- Reads may see stale data temporarily
- Lower latency
- Use case: Social media feeds

### Read-Your-Writes Consistency
- User sees their own writes immediately
- Others may see stale data
- Use case: User profile updates

## Tools and Technologies

### Sharding Solutions
- **Vitess**: MySQL sharding middleware (YouTube scale)
- **Citus**: PostgreSQL extension for sharding
- **MongoDB**: Built-in sharding support
- **CockroachDB**: Distributed SQL with auto-sharding

### Replication Tools
- **MySQL Group Replication**
- **PostgreSQL Streaming Replication**
- **Galera Cluster**: Synchronous multi-master

## Best Practices

1. **Start simple**: Don't shard prematurely
2. **Choose shard key carefully**: Hard to change later
3. **Plan for growth**: Consider future data distribution
4. **Monitor hotspots**: Track shard utilization
5. **Implement proper failover**: Test disaster recovery
6. **Use connection pooling**: Reduce connection overhead
7. **Cache aggressively**: Reduce database load

## When to Scale

| Signal | Action |
|--------|--------|
| Read latency increasing | Add read replicas |
| Write throughput maxed | Consider sharding |
| Storage limits reached | Partition or shard |
| Single region latency | Geographic distribution |

---

*Document Version: 1.0*  
*Category: Database Architecture*  
*Last Updated: January 2026*

