# Shiner Network Access Map

This map visually breaks down how the tags and groups isolate access across your Tailscale network.

## Network Topology

```mermaid
graph TD
    %% Groups & Tags
    ST["group:shiner-tech\n(Reid, Chris, Cody)"]
    SC["tag:shiner-client\n(Dedicated Business Clients)"]
    EC["tag:ern-client\n(ERN Network Clients)"]
    SEC["Client with BOTH\ntag:shiner-client & tag:ern-client"]

    %% Servers
    SS["tag:shiner-server\n(Shiner Connect Servers)"]
    ERN["tag:license-server:8000\n(ERN Memory Network)"]

    %% Connections
    ST ==>|Full Access| SS
    SC -.->|Business Access Only| SS
    EC -.->|ERN Access Only| ERN
    
    %% Multi-tag connections
    SEC -->|Business Access| SS
    SEC -->|ERN Access| ERN
    
    %% Styling
    classDef server fill:#d9534f,color:white,stroke:#333,stroke-width:2px;
    classDef client fill:#5bc0de,color:black,stroke:#333,stroke-width:2px;
    classDef both fill:#9b59b6,color:white,stroke:#333,stroke-width:2px;
    classDef admin fill:#f0ad4e,color:black,stroke:#333,stroke-width:2px;
    
    class SS,ERN server;
    class SC,EC client;
    class ST admin;
    class SEC both;
```

## Summary of Permissions

| Role / Tag | Description | Network Access |
|---|---|---|
| **`group:shiner-tech`** | Admin/Tech team (Reid, Chris, Cody) | Full access to `shiner-server` instances. |
| **`tag:shiner-client`** | Isolated clients (e.g. campground-office) | **ONLY** allowed to talk to `shiner-server`. Completely blocked from seeing other clients or your personal admin devices. |
| **`tag:ern-client`** | ERN-specific clients | **ONLY** allowed to talk to the ERN network on port 8000. |
| **Both Client Tags** | A device assigned both of the above tags | Gets additive access to **both** `shiner-server` and the ERN network, but remains isolated from everything else. |
