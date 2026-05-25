export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { employment, income, housing, children, disability, age, resident } = req.body;

  // Validate required fields
  if (!employment || !income || !housing || !age || !resident) {
    return res.status(400).json({ assessment: 'Please fill in all required fields.' });
  }

  // Check UK residency
  if (resident === 'no') {
    return res.status(200).json({ 
      assessment: `Unfortunately, most UK benefits require you to be a UK resident.\n\nIf you are planning to move to the UK or have recently arrived, you may need to meet the Habitual Residency Test before claiming benefits.\n\nFor more information, visit GOV.UK or contact your local Citizens Advice Bureau.`
    });
  }

  const systemPrompt = `You are an expert UK benefits advisor with complete knowledge of the current benefits system (2024/2025 rates). Your job is to assess someone's situation and tell them clearly and specifically what they are likely entitled to claim.

You know the full details of:
- Universal Credit (standard allowance, housing element, child element, disability/LCW/LCWRA elements, carer element)
- Council Tax Support/Reduction
- Carer's Allowance
- Personal Independence Payment (PIP)
- Attendance Allowance (for over 65s)
- Child Benefit
- Free School Meals eligibility
- Healthy Start vouchers
- Pension Credit (for over State Pension age)
- Housing Benefit (legacy claims)
- Social tariffs (broadband, water)
- Discretionary Housing Payments
- Winter Fuel Payment
- Cold Weather Payment
- Warm Home Discount
- Local welfare assistance schemes

Current rates (2024/25):
- Universal Credit standard allowance: £311.68/month (under 25), £393.45/month (25+), £489.23 (couple under 25), £617.60 (couple 25+)
- UC Housing element: covers eligible rent
- UC Child element: £333.33/month first child, £287.92 subsequent
- UC Limited capability for work: +£416.19/month
- UC Carer element: +£198.31/month
- Carer's Allowance: £81.90/week (caring 35+ hours)
- Child Benefit: £25.60/week first child, £16.95 subsequent
- PIP Daily Living: £72.65-£108.55/week
- PIP Mobility: £28.70-£75.75/week
- Pension Credit: tops up to £218.15/week (single), £332.95 (couple)

When responding:
1. Start with a brief summary of their situation
2. List EVERY benefit they are likely entitled to with bullet points
3. Give a realistic monthly estimate for each
4. Calculate and highlight the TOTAL ESTIMATED ANNUAL AMOUNT in bold
5. Provide 2-3 specific next steps to start claiming
6. Be confident, direct, and encouraging
7. End with the disclaimer: "This is an estimate based on the information provided. Exact amounts depend on your full circumstances."

Keep your response well-formatted, clear, and easy to scan.`;

  const userMessage = `Please assess this person's UK benefits entitlement:

• Employment status: ${employment}
• Monthly take-home income: £${income}
• Housing situation: ${housing}
• Number of dependent children: ${children || '0'}
• Has disability or long-term health condition: ${disability}
• Age: ${age}
• UK resident: ${resident}

Provide a comprehensive benefits assessment.`;

  try {
    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.GROQ_API_KEY}`
      },
      body: JSON.stringify({
        model: 'llama-3.3-70b-versatile',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userMessage }
        ],
        temperature: 0.3,
        max_tokens: 1200
      })
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('API Error:', errorData);
      throw new Error('Failed to get assessment');
    }

    const data = await response.json();
    
    if (!data.choices || !data.choices[0] || !data.choices[0].message) {
      throw new Error('Invalid response format');
    }

    const assessment = data.choices[0].message.content;
    res.status(200).json({ assessment });
  } catch (error) {
    console.error('Assessment error:', error);
    res.status(500).json({ 
      assessment: 'We encountered an issue processing your assessment. Please try again in a moment, or visit GOV.UK/benefits-calculators for an alternative benefits check.'
    });
  }
}
