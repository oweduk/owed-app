export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();

  const { employment, income, housing, children, disability, age, resident } = req.body;

  if (resident === 'no') {
    return res.status(200).json({ 
      assessment: 'Unfortunately, Owed is only available to UK residents. If you move to the UK in future, we\'d love to help you find what you\'re entitled to.',
      qualified: false
    });
  }

  const systemPrompt = `You are an expert UK benefits advisor with complete knowledge of the current benefits system. Your job is to assess someone's situation and tell them clearly and specifically what they are likely entitled to claim.

You know the full details of:
- Universal Credit (standard allowance, housing element, child element, disability/LCW/LCWRA elements, carer element)
- Council Tax Support/Reduction
- Carer's Allowance
- Personal Independence Payment (PIP)
- Child Benefit
- Free School Meals
- Healthy Start vouchers
- Pension Credit
- Housing Benefit
- Social tariffs (broadband, water)
- Discretionary Housing Payments
- Local welfare assistance schemes

Rules you follow:
- Universal Credit standard allowance is £311/month for single under 25, £393/month for single 25+
- Housing element covers eligible rent for private/social renters
- Child element is £287/month for first child, £244 for subsequent children
- Income threshold for UC tapers at 55p per £1 earned above work allowance
- Carer's Allowance is £81.90/week for caring 35+ hours for someone receiving PIP/DLA
- Child Benefit is £25.60/week for first child, £16.95 for subsequent children

When responding:
1. List every benefit they are likely entitled to
2. Give a realistic monthly/annual estimate for each
3. Give a TOTAL estimated annual amount
4. Write 2-3 sentences explaining how to start claiming the most valuable one
5. Be specific, confident and direct — no vague language
6. End with exactly this text on its own line: TOTAL_AMOUNT:[amount in pounds as a number only, no symbols]

Format your response clearly with each benefit on its own line.`;

  const userMessage = `Please assess this person's benefits entitlement:
- Employment status: ${employment}
- Monthly take-home income: £${income}
- Housing: ${housing}
- Dependent children: ${children}
- Disability or long-term health condition: ${disability}
- Age: ${age}
- UK resident: ${resident}`;

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
        max_tokens: 1000
      })
    });

    const data = await response.json();
    const rawAssessment = data.choices[0].message.content;

    const totalMatch = rawAssessment.match(/TOTAL_AMOUNT:(\d+)/);
    const totalAmount = totalMatch ? parseInt(totalMatch[1]) : null;
    const assessment = rawAssessment.replace(/TOTAL_AMOUNT:\s*\d+/g, '').trim();
    const qualified = totalAmount !== null && totalAmount > 0;

    res.status(200).json({ 
      assessment,
      totalAmount,
      qualified
    });
  } catch (error) {
    res.status(500).json({ assessment: 'Something went wrong. Please try again.', qualified: false });
  }
}
