# auditor.py — main audit script

import argparse
import ssl
import ldap3
from datetime import datetime, timezone
from ldap3 import Server, Connection, ALL, SIMPLE, SUBTREE
from config import (
    AD_HOST, AD_DOMAIN, AD_USER, AD_PASSWORD,
    AD_BASE_DN, INACTIVE_DAYS_THRESHOLD
)
from utils import setup_logger, get_timestamp

logger = setup_logger()


def connect_to_ad():
    logger.info(f"Connecting to AD at {AD_HOST}...")
    tls_configuration = ldap3.Tls(validate=ssl.CERT_NONE)
    server = Server(AD_HOST, port=636, use_ssl=True, tls=tls_configuration, get_info=ALL)
    conn = Connection(
        server,
        user="CORP\\Administrator",
        password="Adm1nLab2026",
        authentication=SIMPLE,
        auto_bind=True
    )
    logger.info("Connected successfully.")
    return conn


def get_all_users(conn):
    logger.info("Pulling all users from AD...")
    conn.search(
        search_base=AD_BASE_DN,
        search_filter="(&(objectClass=user)(objectCategory=person))",
        search_scope=SUBTREE,
        attributes=[
            "sAMAccountName",
            "displayName",
            "distinguishedName",
            "memberOf",
            "userAccountControl",
            "lastLogon",
            "lastLogonTimestamp",
            "department",
            "title",
            "description"
        ]
    )
    users = conn.entries
    logger.info(f"Found {len(users)} users.")
    return users


def get_all_groups(conn):
    logger.info("Pulling all groups from AD...")
    conn.search(
        search_base=AD_BASE_DN,
        search_filter="(objectClass=group)",
        search_scope=SUBTREE,
        attributes=["cn", "member", "distinguishedName"]
    )
    return conn.entries


def is_disabled(user):
    uac = int(user.userAccountControl.value or 0)
    return bool(uac & 2)


def get_ou_from_dn(dn):
    parts = str(dn).split(",")
    for part in parts:
        if part.strip().startswith("OU="):
            return part.strip().replace("OU=", "")
    return "Unknown"


def get_last_logon_days(user):
    raw = None
    if user.lastLogonTimestamp and str(user.lastLogonTimestamp) not in ["", "[]"]:
        raw = user.lastLogonTimestamp.value
    elif user.lastLogon and str(user.lastLogon) not in ["", "[]", "0"]:
        raw = user.lastLogon.value

    if raw is None:
        return None

    if isinstance(raw, datetime):
        last = raw.replace(tzinfo=timezone.utc) if raw.tzinfo is None else raw
        now = datetime.now(timezone.utc)
        return (now - last).days

    return None


def check_cross_department_access(users, groups):
    logger.info("Running check: cross-department group memberships...")
    findings = []

    dept_groups = {
        "IT": "GRP_IT_Admins",
        "HR": "GRP_HR_Staff",
        "Finance": "GRP_Finance_Analysts"
    }

    group_dept_map = {v: k for k, v in dept_groups.items()}

    for user in users:
        if is_disabled(user):
            continue

        username = str(user.sAMAccountName)
        user_ou = get_ou_from_dn(str(user.distinguishedName))
        member_of = [str(g) for g in user.memberOf] if user.memberOf else []

        user_groups = []
        for g in member_of:
            for grp_name in group_dept_map:
                if grp_name in g:
                    user_groups.append(grp_name)

        if len(user_groups) > 1:
            findings.append({
                "user": username,
                "display_name": str(user.displayName),
                "ou": user_ou,
                "groups": user_groups,
                "detail": f"{username} is a member of {', '.join(user_groups)} — cross-department access detected."
            })

    logger.info(f"Cross-department check complete. {len(findings)} finding(s).")
    return findings


def check_disabled_in_active_ou(users):
    logger.info("Running check: disabled accounts in active OUs...")
    findings = []
    terminated_ou = "Terminated"

    for user in users:
        if is_disabled(user):
            ou = get_ou_from_dn(str(user.distinguishedName))
            if ou != terminated_ou:
                findings.append({
                    "user": str(user.sAMAccountName),
                    "display_name": str(user.displayName),
                    "ou": ou,
                    "detail": f"{user.sAMAccountName} is disabled but still located in OU={ou}, not in Terminated OU."
                })

    logger.info(f"Disabled accounts check complete. {len(findings)} finding(s).")
    return findings


def check_no_group_memberships(users):
    logger.info("Running check: accounts with no group memberships...")
    findings = []

    for user in users:
        if is_disabled(user):
            continue
        member_of = [str(g) for g in user.memberOf] if user.memberOf else []
        if not member_of:
            findings.append({
                "user": str(user.sAMAccountName),
                "display_name": str(user.displayName),
                "ou": get_ou_from_dn(str(user.distinguishedName)),
                "detail": f"{user.sAMAccountName} has no group memberships — access scope cannot be determined."
            })

    logger.info(f"No group membership check complete. {len(findings)} finding(s).")
    return findings


def check_inactive_accounts(users):
    logger.info(f"Running check: accounts inactive for {INACTIVE_DAYS_THRESHOLD}+ days...")
    findings = []

    for user in users:
        if is_disabled(user):
            continue

        days = get_last_logon_days(user)

        if days is None:
            findings.append({
                "user": str(user.sAMAccountName),
                "display_name": str(user.displayName),
                "ou": get_ou_from_dn(str(user.distinguishedName)),
                "days_inactive": "Never logged in",
                "detail": f"{user.sAMAccountName} has never logged in."
            })
        elif days >= INACTIVE_DAYS_THRESHOLD:
            findings.append({
                "user": str(user.sAMAccountName),
                "display_name": str(user.displayName),
                "ou": get_ou_from_dn(str(user.distinguishedName)),
                "days_inactive": days,
                "detail": f"{user.sAMAccountName} has not logged in for {days} days."
            })

    logger.info(f"Inactive accounts check complete. {len(findings)} finding(s).")
    return findings


def run_audit():
    logger.info("=" * 50)
    logger.info("AD IAM Auditor — Starting audit")
    logger.info(f"Timestamp: {get_timestamp()}")
    logger.info("=" * 50)

    conn = connect_to_ad()
    users = get_all_users(conn)
    groups = get_all_groups(conn)

    results = {
        "timestamp": get_timestamp(),
        "domain": AD_DOMAIN,
        "total_users": len(users),
        "checks": {
            "cross_department": {
                "title": "Cross-Department Group Memberships",
                "severity": "High",
                "findings": check_cross_department_access(users, groups)
            },
            "disabled_in_active_ou": {
                "title": "Disabled Accounts in Active OUs",
                "severity": "Medium",
                "findings": check_disabled_in_active_ou(users)
            },
            "no_group_memberships": {
                "title": "Accounts With No Group Memberships",
                "severity": "Medium",
                "findings": check_no_group_memberships(users)
            },
            "inactive_accounts": {
                "title": "Inactive or Never Logged In Accounts",
                "severity": "High",
                "findings": check_inactive_accounts(users)
            }
        }
    }

    total_findings = sum(len(v["findings"]) for v in results["checks"].values())
    logger.info(f"Audit complete. Total findings: {total_findings}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AD IAM Auditor")
    parser.add_argument("--host", help="AD host IP", default=None)
    parser.add_argument("--domain", help="AD domain", default=None)
    args = parser.parse_args()

    results = run_audit()

    from report import generate_reports
    html_file, pdf_file = generate_reports(results)

    print(f"\n✅ Audit complete.")
    print(f"📄 HTML report: {html_file}")
    print(f"📄 PDF report:  {pdf_file}")