import nodemailer from 'nodemailer';

interface SendOtpResult {
  success: boolean;
  sentViaEmail: boolean;
  message: string;
  code: string;
  error?: string;
}

let cachedTransporter: nodemailer.Transporter | null = null;

function getTransporter(): nodemailer.Transporter | null {
  const user = process.env.GMAIL_USER || process.env.SMTP_USER || process.env.EMAIL_USER;
  const pass = process.env.GMAIL_APP_PASSWORD || process.env.SMTP_PASS || process.env.EMAIL_PASS;

  if (!user || !pass) {
    return null;
  }

  if (!cachedTransporter) {
    const host = process.env.SMTP_HOST || 'smtp.gmail.com';
    const port = Number(process.env.SMTP_PORT) || 465;
    const secure = port === 465;

    cachedTransporter = nodemailer.createTransport({
      host,
      port,
      secure,
      auth: {
        user,
        pass,
      },
    });
  }

  return cachedTransporter;
}

export async function sendOtpEmail(toEmail: string, otpCode: string): Promise<SendOtpResult> {
  const transporter = getTransporter();

  if (!transporter) {
    const hint = 'To deliver real emails to your Gmail inbox when deployed on Render, add GMAIL_USER and GMAIL_APP_PASSWORD to your Render Environment Variables dashboard. In the meantime, your verification code is displayed right here!';
    return {
      success: true,
      sentViaEmail: false,
      code: otpCode,
      message: `Verification code generated: ${otpCode}. ${hint}`,
    };
  }

  try {
    const sender = process.env.GMAIL_USER || process.env.SMTP_USER || 'no-reply@elyanivery.com';
    
    await transporter.sendMail({
      from: `"Elyanivery Doorstep Delivery" <${sender}>`,
      to: toEmail,
      subject: `Elyanivery Verification Code: ${otpCode}`,
      text: `Welcome to Elyanivery!\n\nYour 6-digit verification code is: ${otpCode}\n\nThis code will expire in 10 minutes.\n\nThank you for choosing Elyanivery!`,
      html: `
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 28px 24px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
          <div style="text-align: center; margin-bottom: 20px;">
            <div style="display: inline-block; width: 56px; height: 56px; background: #fff7ed; border-radius: 12px; line-height: 56px; font-size: 28px;">🍕</div>
            <h1 style="color: #ff6b00; font-size: 24px; font-weight: 800; margin: 10px 0 2px 0;">Elyanivery</h1>
            <p style="color: #64748b; font-size: 13px; margin: 0;">Doorstep Delivery &bull; Google Maps Powered</p>
          </div>

          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 20px;">
            <p style="color: #334155; font-size: 14px; margin: 0 0 12px 0;">Use the following 6-digit verification code to complete your registration:</p>
            <div style="font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #0f172a; font-family: monospace; background: #ffffff; border: 2px dashed #ff6b00; border-radius: 8px; padding: 12px 20px; display: inline-block;">
              ${otpCode}
            </div>
            <p style="color: #94a3b8; font-size: 12px; margin: 12px 0 0 0;">Valid for 10 minutes &bull; Do not share this code with anyone</p>
          </div>

          <p style="color: #64748b; font-size: 13px; line-height: 1.5; margin: 0 0 16px 0;">
            If you did not request this registration code on Elyanivery, you can safely disregard this email.
          </p>

          <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 20px 0;" />

          <p style="color: #94a3b8; font-size: 11px; text-align: center; margin: 0;">
            Elyanivery Platform &bull; Egypt &bull; Moldova &bull; Romania
          </p>
        </div>
      `,
    });

    return {
      success: true,
      sentViaEmail: true,
      code: otpCode,
      message: `A 6-digit verification code has been dispatched directly to your Gmail inbox (${toEmail})! Check your inbox or spam folder.`,
    };
  } catch (err: any) {
    console.error('Failed to send email via SMTP transporter:', err);
    return {
      success: true,
      sentViaEmail: false,
      code: otpCode,
      error: err.message,
      message: `Could not reach SMTP server (${err.message}). Verification code for demo/instant registration is: ${otpCode}`,
    };
  }
}
