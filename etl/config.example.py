"""
config.example.py - copy to config.py and fill in for your environment.

The real config.py is gitignored. It holds only non-secret structure (which
collections to pull and which fields to keep); actual secrets - the pseudonym
salt, the GCP token, the project id - come from environment variables, never
from this file.

The allowlist is the first line of defense: a field that is not listed here is
never fetched, so it can never reach the model. PII keys that do get pulled are
dropped or pseudonymized in privacy.py.
"""

# collection -> fields to request from Firestore (field-mask).
# Shown here for a handful of the 32 production collections; the rest follow the
# same shape. Note there is no email / displayName / token field anywhere.
ALLOWLIST = {
    "users": [
        "createdAt", "lastActiveAt", "onboardingComplete", "totalEntered",
        "totalWins", "totalLosses", "rankPoints", "rankTier",
        "acquisition.source", "acquisition.medium", "acquisition.campaign",
        "isOrganizer", "premiumTier", "discordConnections.count",
        "friends.count", "referralCount", "dmOptIn",
    ],
    "tournaments": [
        "title", "game", "status", "format", "startTime", "createdAt",
        "completedAt", "cancelledAt", "registeredCount", "maxSlots",
        "isTest", "visibility", "winnerId", "totalRounds",
    ],
    "registrations": [
        "tournamentId", "userId", "registeredAt", "checkedIn", "checkedInAt",
        "placement", "isEliminated", "isTest", "platform",
    ],
    "matches": [
        "tournamentId", "status", "liveAt", "endedAt", "flowForfeit",
        "disputedAt", "round", "game",
    ],
    # ... metricsDaily, productMetrics, notificationEvents, socialDaily,
    #     featureUsageWeekly, externalTournaments, and ~20 more.
}
