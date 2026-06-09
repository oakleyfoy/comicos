const HELPER_MESSAGE_TYPE = "comicos_midtown_local_sync_capture";
const HELPER_ERROR_TYPE = "comicos_midtown_local_sync_error";
const WINDOW_NAME_TYPE = "comicos_midtown_local_sync";

function helperScriptSource(): string {
  return [
    "(async()=>{",
    "const ok=(data)=>window.opener&&window.opener.postMessage({type:'",
    HELPER_MESSAGE_TYPE,
    "',...data},data.appOrigin);",
    "const fail=(message,data)=>{if(window.opener&&data&&data.appOrigin){window.opener.postMessage({type:'",
    HELPER_ERROR_TYPE,
    "',message,accountId:data.accountId,syncRunId:data.syncRunId},data.appOrigin);}alert(message);};",
    "let syncData;",
    "try{syncData=JSON.parse(window.name||'{}');}catch(error){syncData=null;}",
    "if(!syncData||syncData.type!=='",
    WINDOW_NAME_TYPE,
    "'){fail('Start Midtown browser sync from Comicos first.',syncData);return;}",
    "if(!window.opener||window.opener.closed){fail('Return to Comicos and start Midtown browser sync again.',syncData);return;}",
    "if(!location.hostname.includes('midtowncomics.com')){fail('Open Midtown in your browser before using the Comicos Midtown Sync bookmark.',syncData);return;}",
    "if(!location.pathname.includes('/account/orders')||location.pathname.includes('/view/')){fail('Open the Midtown orders history page, then run the Comicos Midtown Sync bookmark.',syncData);return;}",
    "const abs=(href)=>{try{return new URL(href,location.origin).toString();}catch(error){return null;}};",
    "const links=[...document.querySelectorAll('a[href]')].map((anchor)=>abs(anchor.getAttribute('href')||''))",
    ".filter((href)=>href&&href.includes('/account/orders/')&&!href.endsWith('/account/orders'));",
    "const detailUrls=[...new Set(links)].slice(0,Number(syncData.limitOrders)||25);",
    "if(!detailUrls.length){fail('No Midtown order detail links were found. Make sure the orders page is fully loaded before running the bookmark.',syncData);return;}",
    "const orderNo=(url)=>{const match=String(url).match(/([A-Z0-9-]{5,})$/i);return match?match[1]:null;};",
    "const historyHtml=document.documentElement.outerHTML;",
    "const detailPages=[];",
    "for(const detailUrl of detailUrls){",
    "const response=await fetch(detailUrl,{credentials:'include'});",
    "if(!response.ok){throw new Error('Failed to load Midtown order detail page.');}",
    "detailPages.push({detail_url:detailUrl,fallback_order_number:orderNo(detailUrl),html:await response.text()});",
    "}",
    "ok({appOrigin:syncData.appOrigin,accountId:syncData.accountId,syncRunId:syncData.syncRunId,helperToken:syncData.helperToken,historyHtml,detailPages});",
    "alert('Midtown order data was sent back to Comicos. Return to the Comicos tab to finish the sync.');",
    "})().catch((error)=>{",
    "let syncData;",
    "try{syncData=JSON.parse(window.name||'{}');}catch(parseError){syncData=null;}",
    "const message=error instanceof Error?error.message:'Midtown browser sync failed.';",
    "if(window.opener&&syncData&&syncData.appOrigin){window.opener.postMessage({type:'",
    HELPER_ERROR_TYPE,
    "',message,accountId:syncData.accountId,syncRunId:syncData.syncRunId},syncData.appOrigin);}",
    "alert(message);",
    "});",
  ].join("");
}

export function buildMidtownBookmarkletHref(): string {
  return `javascript:${helperScriptSource()}`;
}

export function isMidtownHelperMessage(data: unknown): data is {
  type: string;
  accountId: number;
  syncRunId: number;
  helperToken?: string;
  historyHtml?: string;
  detailPages?: Array<{ detail_url: string; html: string; fallback_order_number?: string | null }>;
  message?: string;
} {
  if (!data || typeof data !== "object") {
    return false;
  }
  const record = data as Record<string, unknown>;
  return (
    (record.type === HELPER_MESSAGE_TYPE || record.type === HELPER_ERROR_TYPE) &&
    typeof record.accountId === "number" &&
    typeof record.syncRunId === "number"
  );
}

export function midtownHelperMessageType(): string {
  return HELPER_MESSAGE_TYPE;
}

export function midtownHelperErrorType(): string {
  return HELPER_ERROR_TYPE;
}

export function buildMidtownWindowName(payload: {
  accountId: number;
  syncRunId: number;
  helperToken: string;
  limitOrders: number;
  appOrigin: string;
}): string {
  return JSON.stringify({
    type: WINDOW_NAME_TYPE,
    accountId: payload.accountId,
    syncRunId: payload.syncRunId,
    helperToken: payload.helperToken,
    limitOrders: payload.limitOrders,
    appOrigin: payload.appOrigin,
  });
}
