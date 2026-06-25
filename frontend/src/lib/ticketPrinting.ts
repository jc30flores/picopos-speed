import {
  downloadOrderReceiptPdf,
  fetchPaymentTicketBlob,
  printPaymentTicket,
} from "@/lib/api";

export type SmartPrintTicketParams = {
  paymentId?: number | null;
  orderId?: number | null;
  preferDirect?: boolean;
};

export type SmartPrintTicketResult = {
  method: "direct" | "browser";
};

const cleanupBrowserPrint = (iframe: HTMLIFrameElement | null, url: string) => {
  window.setTimeout(() => {
    if (iframe?.parentNode) iframe.parentNode.removeChild(iframe);
    URL.revokeObjectURL(url);
  }, 4000);
};

const printUrlWithPopup = (url: string): Promise<void> => {
  const win = window.open(url, "_blank", "noopener,noreferrer,width=520,height=800");
  if (!win) {
    return Promise.reject(new Error("El navegador bloqueó la impresión. Permite ventanas emergentes e intenta de nuevo."));
  }
  return new Promise((resolve) => {
    win.addEventListener("load", () => {
      win.focus();
      win.print();
      resolve();
    }, { once: true });
    window.setTimeout(resolve, 1500);
  });
};

export const printPdfBlobWithBrowser = async (blob: Blob): Promise<void> => {
  const url = URL.createObjectURL(blob);
  let iframe: HTMLIFrameElement | null = document.createElement("iframe");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  iframe.style.opacity = "0";
  iframe.setAttribute("aria-hidden", "true");

  try {
    await new Promise<void>((resolve, reject) => {
      if (!iframe) return reject(new Error("No se pudo preparar el ticket para impresión."));
      const timer = window.setTimeout(() => reject(new Error("No se pudo preparar el ticket para impresión.")), 5000);
      iframe.onload = () => {
        window.clearTimeout(timer);
        try {
          iframe?.contentWindow?.focus();
          iframe?.contentWindow?.print();
          resolve();
        } catch (error) {
          reject(error instanceof Error ? error : new Error("No se pudo imprimir el ticket. Intenta nuevamente."));
        }
      };
      iframe.onerror = () => {
        window.clearTimeout(timer);
        reject(new Error("No se pudo preparar el ticket para impresión."));
      };
      iframe.src = url;
      document.body.appendChild(iframe);
    });
  } catch (error) {
    if (iframe?.parentNode) iframe.parentNode.removeChild(iframe);
    iframe = null;
    await printUrlWithPopup(url).catch((popupError) => {
      throw popupError instanceof Error ? popupError : error;
    });
  } finally {
    cleanupBrowserPrint(iframe, url);
  }
};

export const smartPrintTicket = async ({ paymentId, orderId, preferDirect = true }: SmartPrintTicketParams): Promise<SmartPrintTicketResult> => {
  if (preferDirect && paymentId) {
    try {
      const directResult = await printPaymentTicket(paymentId);
      if (directResult.printed) return { method: "direct" };
      if (directResult.pdfBlob) {
        await printPdfBlobWithBrowser(directResult.pdfBlob);
        return { method: "browser" };
      }
    } catch {
      // Fall back to browser printing below.
    }
  }

  const blob = paymentId
    ? await fetchPaymentTicketBlob(paymentId)
    : orderId
      ? await downloadOrderReceiptPdf(orderId)
      : null;

  if (!blob) throw new Error("No se encontró un ticket válido para imprimir.");
  await printPdfBlobWithBrowser(blob);
  return { method: "browser" };
};
