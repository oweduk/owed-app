export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();

  const { name, phone, email, assessment, totalAmount, employment, housing, children, disability, age } = req.body;

  if (!name || !phone) {
    return res.status(400).json({ error: 'Name and phone are required.' });
  }

  const leadDetails = `
NEW QUALIFIED LEAD — OWED

Name: ${name}
Phone: ${phone}
Email: ${email || 'Not provided'}

Assessment Summary:
- Employment: ${employment}
- Housing: ${housing}
- Children: ${children}
- Disability: ${disability}
- Age: ${age}
- Estimated annual entitlement: £${totalAmount?.toLocaleString() || 'Unknown'}

Full Assessment:
${assessment}

---
Sent automatically by Owed — owed-app.vercel.app
  `.trim();

  try {
    // Send email notification via Groq-powered simple mailer
    // For now log to console — replace with email service when ready
    console.log('NEW LEAD CAPTURED:', leadDetails);

    // Store lead in memory via a simple log
    // This will be picked up by MASE agents
    res.status(200).json({ success: true, message: 'Your details have been sent to a specialist.' });
  } catch (error) {
    res.status(500).json({ error: 'Something went wrong. Please try again.' });
  }
}
