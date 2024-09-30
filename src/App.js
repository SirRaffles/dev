import React, { useState, useMemo } from 'react';
import { AlertCircle, CheckCircle, Info, ChevronDown, ChevronUp } from 'lucide-react';

const questions = [
  // Financial Performance
  {
    id: 1,
    category: "Financial Performance",
    tagline: "Consistent Growth",
    text: "How many years of consistent revenue growth does your company have?",
    options: ["0-1 year", "2-3 years", "4-5 years", "6+ years"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 2,
    category: "Financial Performance",
    tagline: "Recurring Revenue",
    text: "What percentage of your revenue is recurring?",
    options: ["0-20%", "21-40%", "41-60%", "61-80%", "81-90%", ">90%"],
    scores: [0, 1, 2, 3, 4, 5],
  },
  {
    id: 3,
    category: "Financial Performance",
    tagline: "Revenue Scale",
    text: "What's your company's annual revenue?",
    options: ["<$5 million", "$5-20 million", "$20-50 million", "$50-100 million", ">$100 million"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 4,
    category: "Financial Performance",
    tagline: "Profitability",
    text: "What's your company's EBITDA margin?",
    options: ["<5%", "5-10%", "11-20%", "21-30%", ">30%"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 5,
    category: "Financial Performance",
    tagline: "Rule of 40",
    text: "How well does your company meet the 'Rule of 40' (sum of revenue growth % and EBITDA margin %)?",
    options: ["<20%", "20-30%", "31-40%", ">40%"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 6,
    category: "Financial Performance",
    tagline: "Cash Flow Management",
    text: "How would you rate your company's cash flow management?",
    options: ["Poor", "Adequate", "Good", "Excellent"],
    scores: [0, 1, 2, 3],
  },
  
  // Market Position
  {
    id: 7,
    category: "Market Position",
    tagline: "Client Diversification",
    text: "How diversified is your client base?",
    options: ["Single client", "2-5 major clients", "6-10 major clients", "Well diversified"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 8,
    category: "Market Position",
    tagline: "Market Share",
    text: "What's your company's market share in its primary market?",
    options: ["<5%", "5-10%", "11-20%", "21-30%", ">30%"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 9,
    category: "Market Position",
    tagline: "Brand Recognition",
    text: "How would you rate your company's brand recognition?",
    options: ["Unknown", "Some recognition", "Well-known in niche", "Industry leader"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 10,
    category: "Market Position",
    tagline: "Barriers to Entry",
    text: "How strong are the barriers to entry in your market segment?",
    options: ["Low", "Moderate", "High", "Very High"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 11,
    category: "Market Position",
    tagline: "Client Retention",
    text: "What is your client retention rate?",
    options: ["<70%", "70-80%", "81-90%", ">90%"],
    scores: [0, 1, 2, 3],
  },
  
  // Operations and Efficiency
  {
    id: 12,
    category: "Operations and Efficiency",
    tagline: "Process Documentation",
    text: "How well-documented are your company's processes and procedures?",
    options: ["Not documented", "Partially documented", "Mostly documented", "Fully documented and regularly updated"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 13,
    category: "Operations and Efficiency",
    tagline: "Technology Infrastructure",
    text: "How would you rate your company's technology infrastructure?",
    options: ["Outdated", "Functional but needs upgrading", "Modern and adequate", "Cutting-edge"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 14,
    category: "Operations and Efficiency",
    tagline: "Financial Reporting",
    text: "How effective is your company's financial reporting and controls?",
    options: ["Basic bookkeeping", "Regular unaudited financials", "Annual audited financials", "Quarterly audited financials with strong controls"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 15,
    category: "Operations and Efficiency",
    tagline: "Operational Efficiency",
    text: "How would you rate your company's operational efficiency?",
    options: ["Poor", "Average", "Good", "Excellent", "Best-in-class"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 16,
    category: "Operations and Efficiency",
    tagline: "IP Management",
    text: "How well does your company manage and protect its intellectual property?",
    options: ["No formal IP management", "Basic IP protection", "Comprehensive IP strategy", "Industry-leading IP management"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 17,
    category: "Operations and Efficiency",
    tagline: "Delivery Model",
    text: "How efficient is your company's delivery model?",
    options: ["Inefficient", "Somewhat efficient", "Efficient", "Highly optimized"],
    scores: [0, 1, 2, 3],
  },
  
  // Management and Governance
  {
    id: 18,
    category: "Management and Governance",
    tagline: "Management Stability",
    text: "How stable is your management team?",
    options: ["High turnover", "Some key positions unstable", "Mostly stable", "Very stable with succession plans"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 19,
    category: "Management and Governance",
    tagline: "Corporate Governance",
    text: "How would you describe your company's corporate governance practices?",
    options: ["Minimal", "Basic compliance", "Well-developed", "Best practice governance"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 20,
    category: "Management and Governance",
    tagline: "Risk Management",
    text: "How effective is your company's risk management strategy?",
    options: ["No formal strategy", "Basic risk awareness", "Comprehensive strategy", "Industry-leading risk management"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 21,
    category: "Management and Governance",
    tagline: "Talent Management",
    text: "How would you rate your company's ability to attract and retain top talent?",
    options: ["Struggling", "Average", "Above average", "Industry leader in talent acquisition"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 22,
    category: "Management and Governance",
    tagline: "Equity Participation",
    text: "How widespread is equity participation among key employees?",
    options: ["Limited to founders", "Some key employees", "Most key employees", "Broad-based equity participation"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 23,
    category: "Management and Governance",
    tagline: "Leadership Team Completeness",
    text: "How complete is your leadership team in terms of key roles?",
    options: ["Several key roles missing", "Some gaps", "Most roles filled", "Fully staffed with experienced leaders"],
    scores: [0, 1, 2, 3],
  },
  
  // Innovation and Growth
  {
    id: 24,
    category: "Innovation and Growth",
    tagline: "Product/Service Maturity",
    text: "How mature is your product/service offering?",
    options: ["In development", "Early stage", "Established", "Market-leading", "Disruptive"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 25,
    category: "Innovation and Growth",
    tagline: "Growth Rate",
    text: "How would you describe your company's growth rate compared to the industry average?",
    options: ["Below average", "Average", "Above average", "Far exceeds average"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 26,
    category: "Innovation and Growth",
    tagline: "Innovation Pipeline",
    text: "How would you rate your company's innovation pipeline?",
    options: ["No formal innovation process", "Some innovation efforts", "Strong innovation pipeline", "Disruptive innovator in the industry"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 27,
    category: "Innovation and Growth",
    tagline: "Scalability",
    text: "How scalable is your business model?",
    options: ["Not scalable", "Scalable with significant investment", "Moderately scalable", "Highly scalable"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 28,
    category: "Innovation and Growth",
    tagline: "Competitive Advantage",
    text: "How strong is your company's competitive advantage?",
    options: ["No clear advantage", "Some advantages", "Strong in niche", "Dominant market position"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 29,
    category: "Innovation and Growth",
    tagline: "Market Expansion",
    text: "How actively is your company pursuing market expansion?",
    options: ["No expansion plans", "Considering expansion", "Active expansion in progress", "Successfully expanded to multiple markets"],
    scores: [0, 1, 2, 3],
  },
  
  // Exit Preparedness
  {
    id: 30,
    category: "Exit Preparedness",
    tagline: "Long-term Planning",
    text: "How well-defined is your company's long-term development plan?",
    options: ["No plan", "Basic plan", "Detailed plan", "Comprehensive plan with regular updates"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 31,
    category: "Exit Preparedness",
    tagline: "M&A Process Readiness",
    text: "How well-prepared is your company to handle potential disruptions during the M&A process?",
    options: ["Not prepared", "Somewhat prepared", "Well-prepared", "Fully prepared with contingency plans"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 32,
    category: "Exit Preparedness",
    tagline: "Shareholder Alignment",
    text: "How aligned are your shareholders on the exit strategy and timeline?",
    options: ["Not aligned", "Partially aligned", "Mostly aligned", "Fully aligned"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 33,
    category: "Exit Preparedness",
    tagline: "Due Diligence Readiness",
    text: "How prepared is your management team for due diligence?",
    options: ["Unprepared", "Somewhat prepared", "Well-prepared", "Fully prepared with organized documentation"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 34,
    category: "Exit Preparedness",
    tagline: "Exit Strategy",
    text: "How well-developed is your company's exit strategy?",
    options: ["No strategy", "Basic considerations", "Developed strategy", "Comprehensive strategy with multiple scenarios"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 35,
    category: "Exit Preparedness",
    tagline: "Value Creation Plan",
    text: "How well-developed is your company's value creation plan?",
    options: ["No plan", "Basic plan", "Detailed plan", "Comprehensive plan with regular updates"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 36,
    category: "Exit Preparedness",
    tagline: "Buyer Landscape Understanding",
    text: "How well do you understand the potential buyer landscape for your company?",
    options: ["Limited understanding", "Some knowledge", "Good understanding", "Comprehensive knowledge of potential buyers"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 37,
    category: "Exit Preparedness",
    tagline: "Equity Story",
    text: "How well-developed is your company's equity story for potential investors?",
    options: ["Not developed", "Basic story", "Well-developed story", "Compelling, data-driven equity story"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 38,
    category: "Exit Preparedness",
    tagline: "Transaction Experience",
    text: "How much M&A or capital raising experience does your management team have?",
    options: ["No experience", "Limited experience", "Some experience", "Extensive experience"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 39,
    category: "Exit Preparedness",
    tagline: "Exit Timing",
    text: "How well-timed is your potential exit considering market conditions and company performance?",
    options: ["Poor timing", "Neutral timing", "Good timing", "Optimal timing"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 40,
    category: "Exit Preparedness",
    tagline: "Post-Exit Planning",
    text: "How well-defined are your plans for the business and key employees post-exit?",
    options: ["No plans", "Basic considerations", "Detailed plans", "Comprehensive transition and retention strategy"],
    scores: [0, 1, 2, 3],
  },
];

const detailedRecommendations = {
  "Optimize financial performance": {
    title: "Optimizing Financial Performance",
    steps: [
      "Focus on increasing recurring revenue streams",
      "Implement strategies to improve EBITDA margins",
      "Develop a plan to consistently meet or exceed the Rule of 40",
      "Establish robust financial forecasting and reporting processes",
      "Consider implementing a robust financial forecasting model"
    ]
  },
  "Strengthen market position": {
    title: "Strengthening Market Position",
    steps: [
      "Develop strategies to diversify your client base",
      "Invest in marketing to increase brand recognition",
      "Identify opportunities to increase market share",
      "Develop and communicate a clear, compelling value proposition",
      "Consider strategic partnerships or acquisitions to expand market presence"
    ]
  },
  "Enhance operational efficiency": {
    title: "Enhancing Operational Efficiency",
    steps: [
      "Document and standardize key business processes",
      "Invest in upgrading technology infrastructure",
      "Implement robust financial controls and reporting systems",
      "Develop KPIs to measure and improve operational efficiency",
      "Consider adopting lean or agile methodologies to streamline operations"
    ]
  },
  "Improve management and governance": {
    title: "Improving Management and Governance",
    steps: [
      "Develop succession plans for key management positions",
      "Implement best practice corporate governance structures",
      "Establish a comprehensive risk management framework",
      "Invest in talent acquisition and retention strategies",
      "Consider bringing in experienced board members or advisors"
    ]
  },
  "Accelerate innovation and growth": {
    title: "Accelerating Innovation and Growth",
    steps: [
      "Establish a formal innovation program or R&D department",
      "Develop strategies to outpace industry growth rates",
      "Invest in product/service development to maintain market leadership",
      "Identify opportunities to increase business model scalability",
      "Consider partnerships or acquisitions to access new technologies or markets"
    ]
  },
  "Prepare for exit": {
    title: "Preparing for Exit",
    steps: [
      "Develop a comprehensive long-term strategic plan",
      "Prepare for potential disruptions during the M&A process",
      "Align shareholders on exit strategy and expectations",
      "Prepare comprehensive documentation for due diligence",
      "Develop multiple exit scenarios and strategies"
    ]
  },
};

const ProgressBar = ({ current, total }) => (
  <div className="mb-4 bg-blue-100 rounded p-2">
    <div className="flex items-center">
      <div className="flex-grow bg-blue-200 rounded-full h-2">
        <div
          className="bg-blue-600 rounded-full h-2"
          style={{ width: `${((current + 1) / total) * 100}%` }}
        ></div>
      </div>
      <span className="ml-2 text-sm text-blue-800">
        {current + 1} / {total}
      </span>
    </div>
  </div>
);

const Question = ({ question, onAnswer }) => (
  <div className="mb-4">
    <p className="font-semibold text-gray-900">{question.tagline}: {question.text}</p>
    <div className="flex flex-col space-y-2 mt-2">
      {question.options.map((option, index) => (
        <button
          key={index}
          onClick={() => onAnswer(question.id, question.scores[index])}
          className="px-3 py-2 rounded bg-gray-300 text-gray-800 hover:bg-blue-600 hover:text-white transition-colors"
        >
          {option}
        </button>
      ))}
    </div>
  </div>
);

const RecommendationDetail = ({ recommendation }) => {
  const [isOpen, setIsOpen] = useState(false);
  const detail = detailedRecommendations[recommendation];

  return (
    <div className="mt-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-4 py-2 text-left text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
      >
        <span>{recommendation}</span>
        {isOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
      </button>
      {isOpen && detail && (
        <div className="p-4 mt-2 bg-white rounded shadow">
          <h4 className="font-semibold mb-2">{detail.title}</h4>
          <ul className="list-disc pl-5">
            {detail.steps.map((step, index) => (
              <li key={index} className="mb-1">{step}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

const ExitReadinessAssessment = () => {
  const [answers, setAnswers] = useState({});
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [showEquiteqAdvice, setShowEquiteqAdvice] = useState(false);

  const handleAnswer = (questionId, score) => {
    setAnswers({ ...answers, [questionId]: score });
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
    } else {
      setShowResults(true);
    }
  };

  const { overallScore, categoryScores } = useMemo(() => {
    const categories = [...new Set(questions.map(q => q.category))];
    const categoryScores = categories.reduce((acc, category) => {
      const categoryQuestions = questions.filter(q => q.category === category);
      const totalScore = categoryQuestions.reduce((sum, q) => sum + (answers[q.id] || 0), 0);
      const maxScore = categoryQuestions.reduce((sum, q) => sum + Math.max(...q.scores), 0);
      acc[category] = (totalScore / maxScore) * 100;
      return acc;
    }, {});

    const overallScore = Object.values(categoryScores).reduce((sum, score) => sum + score, 0) / categories.length;

    return { overallScore, categoryScores };
  }, [answers]);

  const getRecommendations = () => {
    const recommendations = [];
    if (categoryScores['Financial Performance'] <= 70) recommendations.push("Optimize financial performance");
    if (categoryScores['Market Position'] <= 70) recommendations.push("Strengthen market position");
    if (categoryScores['Operations and Efficiency'] <= 70) recommendations.push("Enhance operational efficiency");
    if (categoryScores['Management and Governance'] <= 70) recommendations.push("Improve management and governance");
    if (categoryScores['Innovation and Growth'] <= 70) recommendations.push("Accelerate innovation and growth");
    if (categoryScores['Exit Preparedness'] <= 70) recommendations.push("Prepare for exit");
    return recommendations;
  };

  const handleRetake = () => {
    setAnswers({});
    setCurrentQuestion(0);
    setShowResults(false);
    setShowEquiteqAdvice(false);
  };

  const handleEquiteqAdvice = () => {
    setShowEquiteqAdvice(true);
  };

  return (
    <div className="max-w-2xl mx-auto p-4 bg-gray-100 text-gray-900">
      <h1 className="text-2xl font-bold mb-4">Exit Readiness Assessment</h1>
      {!showResults ? (
        <>
          <ProgressBar current={currentQuestion} total={questions.length} />
          <Question
            question={questions[currentQuestion]}
            onAnswer={handleAnswer}
          />
        </>
      ) : (
        <div>
          <h2 className="text-xl font-semibold mb-2">
            Your Overall Exit Readiness Score: {overallScore.toFixed(1)} / 100
          </h2>
          <p className="mb-4">
            {overallScore <= 50 ? (
              <><AlertCircle className="inline mr-2 text-red-600" /> You have significant work to do to prepare for an exit.</>
            ) : overallScore <= 70 ? (
              <><Info className="inline mr-2 text-yellow-600" /> You're on the right track, but there's room for improvement.</>
            ) : overallScore <= 85 ? (
              <><Info className="inline mr-2 text-blue-600" /> You're well-prepared, with some areas for fine-tuning.</>
            ) : (
              <><CheckCircle className="inline mr-2 text-green-600" /> You're exceptionally well-prepared for a potential exit!</>
            )}
          </p>
          
          <div className="mt-4 mb-6">
            <h3 className="text-lg font-semibold mb-2">Category Breakdown:</h3>
            {Object.entries(categoryScores).map(([category, score]) => (
              <div key={category} className="mb-2">
                <div className="flex justify-between items-center mb-1">
                  <h4 className="font-medium">{category}</h4>
                  <span>{score.toFixed(1)} / 100</span>
                </div>
                <div className="bg-gray-200 h-4 rounded-full">
                  <div
                    className="bg-blue-600 h-4 rounded-full"
                    style={{ width: `${score}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          
          <h3 className="text-lg font-semibold mb-2">Recommendations:</h3>
          <div className="space-y-2">
            {getRecommendations().map((rec, index) => (
              <RecommendationDetail key={index} recommendation={rec} />
            ))}
          </div>
          
          <div className="mt-4 space-x-4">
            <button
              onClick={handleRetake}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            >
              Retake Assessment
            </button>
            {overallScore > 80 && (
              <button
                onClick={handleEquiteqAdvice}
                className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
              >
                Get Equiteq Advice
              </button>
            )}
          </div>
          
          {showEquiteqAdvice && (
            <div className="mt-4 p-4 bg-green-100 rounded">
              <h3 className="text-lg font-semibold mb-2">Equiteq's Specialized Advice:</h3>
              <p>
                Congratulations on your high exit readiness score! As the leading M&A advisor for knowledge-based software and services firms, Equiteq is uniquely positioned to guide you through your exit journey. Our expertise can help you:
              </p>
              <ul className="list-disc pl-5 mt-2">
                <li>Leverage our deep market knowledge of the Knowledge Economy to position your company effectively</li>
                <li>Access our extensive network of active buyers and investors in your specific sector</li>
                <li>Benefit from our industry-standard benchmarking studies to optimize your valuation</li>
                <li>Develop a tailored exit strategy that aligns with current market trends and your business goals</li>
                <li>Enhance your equity growth potential through our strategic advisory services</li>
                <li>Prepare comprehensive documentation for due diligence, leveraging our technical transaction expertise</li>
                <li>Navigate complex negotiations with potential acquirers, backed by our emotional intelligence and sector-specific experience</li>
                <li>Gain valuable insights from our detailed market assessments and research reports</li>
              </ul>
              <p className="mt-2">
                Contact Equiteq today to discuss how we can maximize the value of your knowledge-based business and guide you through a successful transaction in the dynamic Knowledge Economy landscape.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ExitReadinessAssessment;