# SEO-NOC User Guide

## Domain Network Management System

**Version:** 3.0  
**Last Updated:** February 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Dashboard](#dashboard)
4. [Asset Domains](#asset-domains)
5. [SEO Networks](#seo-networks)
6. [Alert Center](#alert-center)
7. [Monitoring Settings](#monitoring-settings)
8. [Reports](#reports)
9. [Administration](#administration)
10. [Settings](#settings)

---

## Overview

SEO-NOC is a comprehensive Domain Network Management System designed for managing SEO networks, monitoring domain health, tracking domain expirations, and detecting SEO configuration conflicts.

### Key Features

- **Domain Management**: Track and manage all your domains in one place
- **SEO Network Visualization**: Build and visualize tiered SEO structures
- **Real-time Monitoring**: Monitor domain availability (up/down status)
- **Expiration Tracking**: Get alerts before domains expire
- **Conflict Detection**: Automatically detect SEO misconfigurations
- **Multi-brand Support**: Manage domains across multiple brands
- **Role-based Access**: Control access with user roles and permissions
- **Telegram Notifications**: Receive instant alerts via Telegram

---

## Getting Started

### Logging In

1. Navigate to the application URL
2. Enter your email and password
3. Click **Sign In**

### First-time Setup (Super Admin)

1. Configure branding in **Settings > Branding**
2. Set up Telegram notifications in **Settings > SEO Notifications**
3. Create brands in **Brands** menu
4. Add users and assign roles in **Users** menu
5. Import or add your domains in **Asset Domains**

---

## Dashboard

The dashboard provides a quick overview of your domain portfolio.

### Stats Cards

| Card | Description |
|------|-------------|
| **Domains** | Total number of domains |
| **Networks** | Number of SEO networks |
| **Monitored** | Domains with monitoring enabled (up/down count) |
| **Index Rate** | Percentage of indexed domains |
| **Active Alerts** | Unacknowledged alerts |
| **Brands** | Number of brands |

### Critical Alerts Banner

When domains are down, a red banner appears showing:
- Number of critical alerts
- Affected domain names (up to 3)
- Quick link to **View Alerts**

> **Note:** Banner automatically disappears when domains come back up.

### Monitoring Status Chart

Pie chart showing:
- **Green**: Domains that are UP
- **Red**: Domains that are DOWN

### Recent Alerts

Shows the latest monitoring and expiration alerts. Click **View All** to see all alerts in the Monitoring Settings page.

---

## Asset Domains

Manage all your domains from the Asset Domains page.

### Adding a Domain

1. Click **+ Add Domain**
2. Fill in the details:
   - **Domain**: e.g., `example.com`
   - **Brand**: Select the brand
   - **Status**: Active/Inactive
   - **Expiration Date**: When the domain expires
3. Click **Save**

### Domain Properties

| Field | Description |
|-------|-------------|
| Domain | The domain name |
| Brand | Associated brand |
| Status | Active or Inactive |
| SEO Networks | Networks this domain belongs to |
| Monitoring | ON/OFF - availability monitoring |
| Expiration | Domain expiration date |

### Enabling Monitoring

1. Click the **Edit** button on a domain
2. Toggle **Enable Monitoring** to ON
3. Save changes

### Deleting Domains

> **Important:** Domains that are used in SEO Networks cannot be deleted. Remove them from all networks first.

---

## SEO Networks

Build and manage tiered SEO link structures.

### Understanding Tiers

| Tier | Role | Description |
|------|------|-------------|
| **Tier 0** | Money Site | Your main website |
| **Tier 1** | Primary Support | Direct links to money site |
| **Tier 2** | Secondary Support | Links to Tier 1 sites |
| **Tier 3+** | Additional Tiers | Links to higher tiers |

### Creating a Network

1. Go to **SEO Networks**
2. Click **+ New Network**
3. Enter network name and description
4. Select a brand
5. Click **Create**

### Adding Domains to Network

1. Open a network
2. Click **+ Add Entry**
3. Select the domain
4. Set the tier level
5. Configure link target (which domain it links to)
6. Save

### Network Visualization

The network graph shows:
- **Nodes**: Domains in the network
- **Edges**: Link relationships
- **Colors**: Different tiers are color-coded

### Conflict Detection

The system automatically detects:

| Conflict Type | Description |
|---------------|-------------|
| **Orphan Node** | Domain not linked to any other domain |
| **Tier Inversion** | Lower tier linking to higher tier |
| **Keyword Cannibalization** | Multiple domains targeting same keywords |
| **Canonical Mismatch** | Conflicting canonical configurations |

---

## Alert Center

View and manage SEO conflicts.

### Tracked Conflicts

The conflicts table shows:
- **Type**: Conflict type (Orphan Node, etc.)
- **Severity**: Critical, High, Medium, Low
- **Status**: Detected, In Progress, Resolved
- **Node**: Affected domain
- **Network**: Associated network
- **Detected/Resolved**: Timestamps
- **Action**: View linked optimization task

### Status Tabs

Filter conflicts by status:
- **All**: All conflicts
- **Detected**: New conflicts
- **In Progress**: Being worked on
- **Resolved**: Fixed conflicts

### Creating Optimization Tasks

1. Click **Create Optimization Tasks** to auto-generate tasks
2. Or click **Create Task** on individual conflicts
3. Tasks appear in the Optimizations module

---

## Monitoring Settings

Configure domain monitoring and view alerts.

### Availability Monitoring

Shows current status:
- **Up**: Domains responding normally
- **Down**: Domains not responding

### Tabs

| Tab | Description |
|-----|-------------|
| **Expiration Monitoring** | Configure expiration alerts |
| **Availability Monitoring** | Configure availability checks |
| **Expiring Domains** | List of domains expiring soon |
| **Down Domains** | List of domains currently down |
| **Test Alerts** | Send test notifications |
| **SEO Monitoring** | SEO-specific monitoring |

### Expiration Alert Settings

- **Alert Window**: Days before expiration to alert (e.g., 7 days)
- **Alert Thresholds**: Specific day markers (30, 14, 7, 3, 1 days)
- **Include Auto-Renew**: Also alert for auto-renewing domains

### Manual Checks

- **Check Expirations**: Manually check all domain expirations
- **Check Availability**: Manually ping all monitored domains

---

## Reports

### Conflict Resolution Dashboard

Access via **Reports > Conflict Resolution Dashboard**

Metrics displayed:
- **Total Conflicts**: All detected conflicts
- **Resolution Rate**: Percentage resolved
- **Average Resolution Time**: Time to fix conflicts
- **Recurring Conflicts**: Conflicts that reappear
- **Conflicts by Severity**: Breakdown by priority
- **Conflicts by Type**: Breakdown by conflict type
- **Top Resolvers**: Users who resolved most conflicts

### Other Reports

- **Tier Distribution**: Domain distribution across tiers
- **Network Health**: Overall network status
- **Monitoring Summary**: Up/down statistics

---

## Administration

### Brands

Organize domains by brand/client.

1. Go to **Brands**
2. Click **+ Add Brand**
3. Enter brand name
4. Assign users who can access this brand

### Users

Manage user accounts and permissions.

#### User Roles

| Role | Permissions |
|------|-------------|
| **Super Admin** | Full access to everything |
| **Manager** | Manage domains, networks, view reports |
| **Viewer** | View-only access |

#### Adding Users

1. Go to **Users**
2. Click **+ Add User**
3. Enter email and name
4. Select role
5. Assign brand access
6. Click **Create**

### Categories & Registrars

- **Categories**: Organize domains by category
- **Registrars**: Track domain registrars

---

## Settings

### Branding

Customize the application appearance:

| Setting | Description |
|---------|-------------|
| **Site Title** | App name (e.g., `SEO//NOC`) |
| **Tagline** | Short description |
| **Site Description** | SEO meta description |
| **Logo** | Upload custom logo |

> **Tip:** Use `//` in the title for styled separator (e.g., `SEO//NOC`)

### Timezone

Set the default timezone for all date/time displays.

### SEO Notifications (Telegram)

Configure Telegram alerts for SEO events:

1. Create a Telegram bot via @BotFather
2. Get the bot token
3. Get your chat ID
4. Enter in settings
5. Click **Test Connection**

### Domain Monitoring (Telegram)

Separate Telegram settings for domain monitoring alerts:
- Domain down notifications
- Expiration warnings

### Email Alerts

Configure email notifications:
- Global admin emails
- Severity threshold
- Include network managers

### Templates

Customize notification message templates.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + K` | Quick search |
| `Esc` | Close dialogs |

---

## Troubleshooting

### Domain Shows "No monitored domains"

- Ensure monitoring is enabled on at least one domain
- Refresh the page

### Alerts Not Disappearing

- Critical alert banner only shows for domains currently DOWN
- Banner auto-updates when domains recover

### Cannot Delete Domain

- Domain is used in an SEO Network
- Remove from all networks first, then delete

### Telegram Notifications Not Working

1. Verify bot token is correct
2. Verify chat ID is correct
3. Make sure you've started a chat with the bot
4. Use **Test Connection** to verify

---

## Support

For technical support or feature requests, contact your system administrator.
