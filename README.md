# AD IAM Auditor
### Live Active Directory Security Auditing — Automated PDF & HTML Report Generation

![Platform](https://img.shields.io/badge/Platform-Active_Directory-blue)
![Language](https://img.shields.io/badge/Language-Python_3-green)
![Protocol](https://img.shields.io/badge/Protocol-LDAPS-orange)
![Status](https://img.shields.io/badge/Status-Complete-brightgreen)

---

## Overview

AD IAM Auditor is a Python tool that connects live to an Active Directory environment via LDAPS, pulls all user and group data, runs four automated IAM security checks, and generates professional audit reports in both PDF and HTML format.

Built to automate the kind of manual access review work that security and IAM teams do regularly — identifying privilege drift, orphaned accounts, and access policy violations across an AD domain.

---

## Features

- **Live LDAPS connection** to Active Directory — no CSV exports, no manual queries
- **4 automated audit checks** covering the most common IAM risk areas
- **PDF report** — clean, formatted, ready to share with a security team
- **HTML report** — styled, browser-viewable, same content as PDF
- **Timestamped output** — every run generates a new dated report in `/reports`
- **Structured logging** — full audit trail of every check run

---

## Audit Checks

| Check | Severity | What It Catches |
|---|---|---|
| Cross-Department Group Memberships | High | Users holding group memberships outside their home department — privilege drift |
| Disabled Accounts in Active OUs | Medium | Disabled accounts not moved to Terminated OU — cleanup and compliance gap |
| Accounts With No Group Memberships | Medium | Enabled accounts with no group access — orphaned or misconfigured accounts |
| Inactive / Never Logged In Accounts | High | Accounts with no login in 90+ days or never logged in — stale access risk |

---

## Sample Reports

| Report | Format |
|---|---|
| [sample_report.pdf](./sample_report.pdf) | PDF — open directly in browser |

---

## Screenshots

### Script Running — Live LDAPS Connection & Audit Execution
![Script Running](screenshots/05_script_running.png)
> Live connection to AD at 192.168.56.103 via LDAPS. 14 users pulled, 4 checks executed, 14 total findings, both reports generated.

### HTML Report — Summary Dashboard & Findings
![HTML Report](screenshots/06_html_report.png)
> Auto-generated HTML report showing summary cards and Cross-Department findings — Bob Harris (IT) in Finance group, David Kim (HR) in IT Admins group.

### PDF Report — Formatted Audit Deliverable
![PDF Report](screenshots/07_pdf_report.png)
> Auto-generated PDF report with summary table, severity-coded findings sections, and full detail per check.

---

## Technical Implementation

### LDAPS Over Plain LDAP

This tool connects exclusively over **LDAPS (port 636)** rather than plain LDAP (port 389). This was a deliberate architectural decision — not a convenience choice.

Plain LDAP transmits credentials and directory data in cleartext. Any tool querying AD over port 389 in a production environment is introducing credential interception risk on the wire. LDAPS wraps the entire session in TLS, encrypting both the bind operation and all subsequent query results.

To enable LDAPS on the Windows Server 2025 domain controller:

- Installed Active Directory Certificate Services (AD CS)
- Generated a self-signed certificate bound to the DC's FQDN (`WIN-AJDMOM74UU3.corp.local`)
- Copied the certificate into the NTDS Personal certificate store via the Windows registry — the specific store AD DS reads when initializing LDAPS on startup
- Restarted the NTDS service to force the certificate reload
- Verified the binding using `openssl s_client` from the Linux client before attempting programmatic connection

On the Python side, TLS is configured with `ldap3.Tls(validate=ssl.CERT_NONE)` to allow the self-signed cert in the lab environment. In a production deployment this would be replaced with a CA-signed cert and full chain validation.

### AD Authentication

Windows Server 2025 enforces **LDAP signing and channel binding** by default — a security hardening measure that prevents unsigned LDAP connections. This meant standard simple authentication over plain LDAP was rejected at the protocol level regardless of credentials.

The solution was to implement authentication over LDAPS, which satisfies the channel binding requirement through TLS rather than LDAP signing. This is actually the more secure approach — the server's signing requirement exists precisely to push clients toward encrypted transports.

Group Policy was audited during this process (`Default Domain Controllers Policy → LDAP server signing requirements`) to confirm the policy state and document the security baseline.

### Certificate Store Binding

AD DS doesn't automatically pick up certificates placed in the standard machine certificate store (`LocalMachine\My`). It reads from a specific NTDS-scoped certificate store in the registry:

```
HKLM\SOFTWARE\Microsoft\Cryptography\Services\NTDS\SystemCertificates\My\Certificates
```

The certificate was explicitly copied to this location via PowerShell to ensure AD DS loaded it on service restart. This is a non-obvious requirement that catches most practitioners who haven't done LDAPS configuration from scratch before.

### Report Generation Architecture

The reporting layer is intentionally separated from the audit logic. `auditor.py` handles AD connectivity and check execution and returns a structured Python dictionary of results. `report.py` consumes that dictionary and produces both output formats independently.

This separation means the audit logic can be reused, extended, or piped to other outputs (JSON, Slack, email) without touching the report code — and the report templates can be updated without touching audit logic.

PDF generation uses `reportlab` for programmatic layout control. HTML generation uses `jinja2` templating, keeping the presentation layer clean and modifiable without touching Python code.

---

## Challenges & Solutions

### Challenge 1 — LDAP Signing Enforcement
**Problem:** Windows Server 2025 rejects unsigned LDAP binds by default, returning `strongerAuthRequired` on every connection attempt regardless of credential format.

**What was tried:** NTLM authentication, SIMPLE authentication, SASL DIGEST-MD5, SASL GSSAPI with Kerberos ticket acquisition via `kinit` — all rejected at the protocol level before credentials were even evaluated.

**Solution:** The root cause wasn't authentication method — it was transport. Moving to LDAPS (port 636) resolved the signing requirement entirely because TLS satisfies channel binding at the transport layer. The lesson: when AD returns `strongerAuthRequired`, the answer is usually the transport, not the auth method.

### Challenge 2 — LDAPS Certificate Binding
**Problem:** After enabling LDAPS and generating a certificate, the SSL handshake was still failing with `connection reset by peer` — port 636 was open but AD DS wasn't serving the certificate.

**Root cause:** AD DS reads certificates from a service-specific registry path, not the standard machine certificate store. A certificate present in `LocalMachine\My` is invisible to the NTDS service.

**Solution:** Explicitly copied the certificate thumbprint into `HKLM\SOFTWARE\Microsoft\Cryptography\Services\NTDS\SystemCertificates\My\Certificates` via PowerShell and restarted the NTDS service. Verified the binding using `openssl s_client` before attempting Python connection — zero bytes read meant no cert served; 1374 bytes read confirmed successful TLS handshake.

### Challenge 3 — Python 3.14 + ldap3 NTLM Dependency
**Problem:** `ldap3`'s NTLM implementation requires MD4 hashing via `pycryptodome`. Python 3.14 removed MD4 from the standard `hashlib` due to its deprecated cryptographic status, breaking the default NTLM auth path.

**Solution:** Installed `pycryptodome` to restore the MD4 dependency. This is worth noting for anyone running this tool on Python 3.14+ — add `pycryptodome` to `requirements.txt` regardless of auth method chosen.

---

## Project Structure

```
ad-iam-auditor/
├── auditor.py          # Main script — LDAPS connection, audit logic, CLI
├── report.py           # Report generator — PDF (reportlab) + HTML (jinja2)
├── utils.py            # Shared helpers — logging, timestamps, severity colors
├── config.py           # AD connection settings — host, domain, credentials
├── config.example.py   # Template for config.py
├── requirements.txt    # Dependencies
├── reports/            # Generated reports (timestamped per run)
├── screenshots/        # Documentation screenshots
└── sample_report.pdf   # Pre-generated sample report
```

---

## Tech Stack

| Library | Purpose |
|---|---|
| `ldap3` | LDAPS connection and AD queries |
| `reportlab` | PDF report generation |
| `jinja2` | HTML report templating |
| `pycryptodome` | MD4 hashing for NTLM (required on Python 3.14+) |
| `argparse` | CLI argument handling |
| `logging` | Structured audit logging |
| `ssl` | TLS configuration for LDAPS |

---

## Setup & Usage

### Prerequisites
- Python 3.10+
- Access to an Active Directory domain controller
- LDAPS (port 636) enabled on the DC
- AD account with read permissions

### Install

```bash
git clone https://github.com/CodeBroKinty/ad-iam-auditor.git
cd ad-iam-auditor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy `config.example.py` to `config.py` and fill in your AD connection details:

```python
AD_HOST = "your-dc-ip"
AD_DOMAIN = "your.domain"
AD_USER = "DOMAIN\\username"
AD_PASSWORD = "yourpassword"
AD_BASE_DN = "DC=your,DC=domain"
INACTIVE_DAYS_THRESHOLD = 90
```

### Run

```bash
python auditor.py
```

Reports are saved to `/reports` with a timestamp in the filename.

---

## How It Works

```
python auditor.py

1. Connects to AD via LDAPS (port 636) using TLS
2. Pulls all user objects with attributes:
   sAMAccountName, displayName, distinguishedName,
   memberOf, userAccountControl, lastLogon, department
3. Pulls all group objects
4. Runs 4 audit checks against the data
5. Passes findings to report generator
6. Outputs PDF and HTML reports to /reports
```

---

## Security Notes

- Connects via **LDAPS (port 636)** — encrypted transport, no plaintext credentials on the wire
- Self-signed cert support via `ssl.CERT_NONE` — replace with CA-signed cert and full validation in production
- Credentials stored in `config.py` — excluded from version control via `.gitignore`
- Audit logic is **read-only** — no writes to AD at any point

---

## Related Projects

- [Active Directory IAM Lab](https://github.com/CodeBroKinty/active-directory-iam-lab) — The AD environment this tool was built and tested against

---

*Built by Kiante | 2026 | Python · ldap3 · Active Directory · LDAPS*
