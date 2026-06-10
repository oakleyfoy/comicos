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
    "const abs=(href)=>{try{return new URL(href,location.origin).toString();}catch(error){return null;}};",
    "const orderAnchors=[...document.querySelectorAll('a[href]')].map((anchor)=>{const rawHref=anchor.getAttribute('href')||'';const href=rawHref.toLowerCase().startsWith('javascript:')?rawHref:abs(rawHref);const text=(anchor.textContent||'').trim();const jsMatch=rawHref.match(/ord_info\\((\\d+),\\s*['\\\"]?([^'\\\")]+)['\\\"]?\\)/i);return {href,text,rawHref,orderNumber:jsMatch?jsMatch[1]:null,ordFlag:jsMatch?jsMatch[2]:null};})",
    ".filter(({href,text,orderNumber})=>href&&text&&!/view all/i.test(text)&&((/^[0-9]{5,}$/.test(text))||Boolean(orderNumber)||(/^[a-z]+:\\/\\//i.test(String(href))&&new URL(String(href)).hostname.includes('midtowncomics.com'))));",
    "const detailTargets=[];",
    "for(const anchor of orderAnchors){",
    "if(anchor.orderNumber){detailTargets.push({mode:'ord_info',orderNumber:anchor.orderNumber,ordFlag:anchor.ordFlag||'0',label:anchor.text,rawHref:anchor.rawHref});continue;}",
    "if(typeof anchor.href==='string'&&/^[a-z]+:\\/\\//i.test(anchor.href)&&anchor.href!==location.href&&((/\\/account-orders\\//.test(anchor.href))||(/\\/account\\/orders\\//.test(anchor.href))||(/\\/account-settings/.test(anchor.href)&&(/order/i.test(anchor.text)||/#?order/i.test(anchor.href))))){detailTargets.push({mode:'url',detail_url:anchor.href,label:anchor.text});}",
    "}",
    "const uniqueTargets=[];const seenTargets=new Set();",
    "for(const target of detailTargets){const key=target.mode==='ord_info'?`ord:${target.orderNumber}:${target.ordFlag}`:`url:${target.detail_url}`;if(!seenTargets.has(key)){seenTargets.add(key);uniqueTargets.push(target);}}",
    "const targets=uniqueTargets.slice(0,Number(syncData.limitOrders)||25);",
    "if(!targets.length){fail('No Midtown order detail links were found. Make sure the My Orders table is fully visible before running the bookmark.',syncData);return;}",
    "const orderNo=(url)=>{const match=String(url).match(/([A-Z0-9-]{5,})$/i);return match?match[1]:null;};",
    "const historyHtml=document.documentElement.outerHTML;",
    "const detailPages=[];",
    "const describeError=(error)=>{if(error instanceof Error&&error.message){return error.message;}if(typeof error==='string'&&error){return error;}if(error&&typeof error==='object'&&typeof error.message==='string'&&error.message){return error.message;}try{const text=JSON.stringify(error);if(text&&text!=='{}'){return text;}}catch(jsonError){}return 'Midtown browser sync failed.';};",
    "const waitForLoaded=(win)=>new Promise((resolve,reject)=>{const started=Date.now();const tick=()=>{try{if(!win||win.closed){reject(new Error('Midtown detail window closed before capture finished.'));return;}if(win.document&&win.document.readyState==='complete'){resolve();return;}}catch(error){}if(Date.now()-started>15000){reject(new Error('Timed out waiting for Midtown order detail page.'));return;}setTimeout(tick,200);};tick();});",
    "const isDetailHtml=(win)=>{const html=win.document.documentElement.outerHTML;const text=(win.document.body&&win.document.body.innerText||'').toLowerCase();return text.includes('item status')||text.includes('line total')||text.includes('cover artist')||html.includes('/product/');};",
    "const waitForDetailPage=(win,beforeHtml,beforeUrl,orderNumber)=>new Promise((resolve,reject)=>{const started=Date.now();const tick=()=>{try{if(!win||win.closed){reject(new Error('Midtown detail window closed before capture finished.'));return;}if(!win.document||win.document.readyState!=='complete'){setTimeout(tick,250);return;}const afterUrl=win.location.href;const afterHtml=win.document.documentElement.outerHTML;const changed=afterUrl!==beforeUrl||afterHtml!==beforeHtml;if((changed||isDetailHtml(win))&&isDetailHtml(win)){resolve();return;}}catch(error){}if(Date.now()-started>15000){reject(new Error(`Timed out opening Midtown order ${orderNumber} details.`));return;}setTimeout(tick,250);};tick();});",
    "const captureOrdInfoTarget=async(target)=>{const detailWin=window.open(location.href,'_blank','noopener=no,width=1280,height=900');if(!detailWin){throw new Error('Allow pop-ups so Comicos can capture Midtown order details.');}await waitForLoaded(detailWin);const rawPattern=new RegExp(`ord_info\\\\(${target.orderNumber}\\\\s*,\\\\s*['\\\"]?${target.ordFlag||'0'}['\\\"]?\\\\)`,'i');const findAnchor=(win)=>[...win.document.querySelectorAll('a[href]')].find((node)=>{const raw=node.getAttribute('href')||'';const text=(node.textContent||'').trim();return rawPattern.test(raw)||(text===target.label&&/^[0-9]{5,}$/.test(text));});let popupWin=null;const originalOpen=typeof detailWin.open==='function'?detailWin.open.bind(detailWin):null;if(originalOpen){detailWin.open=(...args)=>{popupWin=originalOpen(...args);return popupWin;};}const anchor=findAnchor(detailWin);const beforeUrl=detailWin.location.href;const beforeHtml=detailWin.document.documentElement.outerHTML;try{if(anchor&&typeof anchor.click==='function'){anchor.click();}else if(anchor){anchor.dispatchEvent(new detailWin.MouseEvent('click',{bubbles:true,cancelable:true,view:detailWin}));}else if(typeof detailWin.ord_info==='function'){detailWin.ord_info(target.orderNumber,target.ordFlag||'0');}else if(typeof target.rawHref==='string'&&target.rawHref.toLowerCase().startsWith('javascript:')&&typeof detailWin.eval==='function'){detailWin.eval(target.rawHref.replace(/^javascript:/i,''));}else{throw new Error(`Midtown order ${target.orderNumber} link was not found on the opened page.`);}}finally{if(originalOpen){detailWin.open=originalOpen;}}if(popupWin){await waitForLoaded(popupWin);await waitForDetailPage(popupWin,'',popupWin.location.href,target.orderNumber);const detailUrl=popupWin.location.href;const html=popupWin.document.documentElement.outerHTML;popupWin.close();detailWin.close();return {detail_url:detailUrl,fallback_order_number:target.orderNumber,html};}await waitForDetailPage(detailWin,beforeHtml,beforeUrl,target.orderNumber);const detailUrl=detailWin.location.href;const html=detailWin.document.documentElement.outerHTML;detailWin.close();return {detail_url:detailUrl,fallback_order_number:target.orderNumber,html};};",
    "for(const target of targets){",
    "if(target.mode==='url'){const response=await fetch(target.detail_url,{credentials:'include'});if(!response.ok){throw new Error('Failed to load Midtown order detail page.');}detailPages.push({detail_url:target.detail_url,fallback_order_number:orderNo(target.detail_url),html:await response.text()});continue;}",
    "detailPages.push(await captureOrdInfoTarget(target));",
    "}",
    "ok({appOrigin:syncData.appOrigin,accountId:syncData.accountId,syncRunId:syncData.syncRunId,helperToken:syncData.helperToken,historyHtml,detailPages});",
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
