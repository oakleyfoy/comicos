export const COLLECTOR_ADVISOR_SUBTITLE = "Your personal comic collecting coach.";

export const COLLECTOR_ADVISOR_PAGE_DESCRIPTION =
  "A prioritized daily action plan built from your collection, market signals, and release calendar.";

export const COLLECTOR_ADVISOR_ANALYSIS_INTRO = "ComicOS analyzes:";

export const COLLECTOR_ADVISOR_ANALYSIS_BULLETS = [
  "Buy opportunities",
  "Sell opportunities",
  "Grading candidates",
  "Marketplace activity",
  "Upcoming releases",
] as const;

export const COLLECTOR_ADVISOR_PLAN_PITCH =
  "to build a personalized daily action plan.";

export const COLLECTOR_ADVISOR_TRY_AGAIN_CTA = "Try Again";

export const COLLECTOR_ADVISOR_STATUS = {
  NO_SNAPSHOT: "NO_SNAPSHOT",
  EMPTY_NO_COLLECTION: "EMPTY_NO_COLLECTION",
  EMPTY_NO_SIGNALS: "EMPTY_NO_SIGNALS",
  EMPTY_GATHER_FAILED: "EMPTY_GATHER_FAILED",
  OK: "OK",
} as const;

export type CollectorAdvisorStatus = (typeof COLLECTOR_ADVISOR_STATUS)[keyof typeof COLLECTOR_ADVISOR_STATUS];

export const COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_SIGNALS =
  "ComicOS reviewed your current collection signals. No buy, sell, grade, or watch actions need attention right now.";

export const COLLECTOR_ADVISOR_GENERATE_PLAN_CTA = "Generate New Plan";

export const COLLECTOR_ADVISOR_TODAYS_BEST_ACTIONS_TITLE = "Today's Best Actions";

export const COLLECTOR_ADVISOR_OPPORTUNITY_VALUE_TITLE = "Today's Opportunity Value";

export const COLLECTOR_ADVISOR_EMPTY_SECTIONS_MESSAGE =
  "No sell, grade, watch, or market alerts require attention today.";

export const COLLECTOR_ADVISOR_NO_OPPORTUNITY_VALUE = "No quantified opportunity value yet.";

export const COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_COLLECTION =
  "Import comics to unlock personalized recommendations.";

export const COLLECTOR_ADVISOR_MESSAGE_GATHER_FAILED =
  "ComicOS could not finish building your Advisor plan. Try again.";

export const COLLECTOR_ADVISOR_NO_PLAN_MESSAGE =
  "Generate your first Advisor plan to see today's buy, sell, grade, and watch actions.";

export const COLLECTOR_ADVISOR_GENERATE_CTA = "Generate My First Plan";

export const COLLECTOR_ADVISOR_OPEN_PLAN_CTA = "Open Latest Plan";

export type AdvisorCapabilityKey = "buy" | "sell" | "grade" | "watch";

export const ADVISOR_CAPABILITY_CARDS: {
  key: AdvisorCapabilityKey;
  title: string;
  blurb: string;
  icon: string;
}[] = [
  {
    key: "buy",
    title: "Buy",
    blurb: "Deals and gaps worth adding to your collection.",
    icon: "🛒",
  },
  {
    key: "sell",
    title: "Sell",
    blurb: "Books to list when the market is in your favor.",
    icon: "💰",
  },
  {
    key: "grade",
    title: "Grade",
    blurb: "Candidates where grading could unlock value.",
    icon: "📋",
  },
  {
    key: "watch",
    title: "Watch",
    blurb: "Releases and titles to keep on your radar.",
    icon: "👁",
  },
];
