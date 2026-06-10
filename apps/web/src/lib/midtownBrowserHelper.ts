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
    "const pageText=(document.body&&document.body.innerText||'').toLowerCase();",
    "const hasOrderTableText=(pageText.includes('my orders')&&(pageText.includes('order #')||pageText.includes('order number'))&&pageText.includes('date')&&pageText.includes('total'))||pageText.includes('orders in process')||pageText.includes('orders processed / shipped & completed')||pageText.includes('order date');",
    "const onOrderHistoryPage=hasOrderTableText&&!location.pathname.includes('/view/');",
    "if(!onOrderHistoryPage){fail('Open the Midtown page that shows My Orders or your account order history, then run the Comicos Midtown Sync bookmark.',syncData);return;}",
    "const pageHtml=document.documentElement.outerHTML;",
    "const pageText=(document.body&&document.body.innerText||'').toLowerCase();",
    "const describeError=(error)=>{if(error instanceof Error&&error.message){return error.message;}if(typeof error==='string'&&error){return error;}if(error&&typeof error==='object'&&typeof error.message==='string'&&error.message){return error.message;}try{const text=JSON.stringify(error);if(text&&text!=='{}'){return text;}}catch(jsonError){}return 'Midtown browser sync failed.';};",
    "const captureDetailNumber=()=>{const match=pageText.match(/order\\s*#\\s*([a-z0-9-]+)/i)||pageHtml.match(/order\\s*#\\s*([a-z0-9-]+)/i);return match&&match[1]?match[1].trim():null;};",
    "const orderNumber=captureDetailNumber();",
    "const looksLikeDetailPage=pageText.includes('order #')&&(pageText.includes('tracking info')||pageText.includes('item status')||pageText.includes('order item details'));",
    "if(!looksLikeDetailPage){fail('Open the Midtown order detail page for the order you want imported, then click the Comicos Midtown Sync bookmark again.',syncData);return;}",
    "ok({appOrigin:syncData.appOrigin,accountId:syncData.accountId,syncRunId:syncData.syncRunId,helperToken:syncData.helperToken,historyHtml:pageHtml,detailPages:[{detail_url:location.href,retailer_order_number:orderNumber,fallback_order_number:orderNumber,html:pageHtml}]});",
    "alert('Midtown order data was sent back to Comicos. Return to the Comicos tab to finish the sync.');",
    "})().catch((error)=>{",
    "let syncData;",
    "try{syncData=JSON.parse(window.name||'{}');}catch(parseError){syncData=null;}",
    "const message=describeError(error);",
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
  detailPages?: Array<{
    detail_url: string;
    html: string;
    retailer_order_number?: string | null;
    fallback_order_number?: string | null;
  }>;
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
