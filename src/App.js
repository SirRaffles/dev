import React, { useState, useMemo } from 'react';
import { AlertCircle, CheckCircle, Info, ChevronDown, ChevronUp } from 'lucide-react';

const questions = [
  {
    id: 1,
    text: "How many years of consistent revenue growth does your company have?",
    options: ["0-1 year", "2-3 years", "4-5 years", "6+ years"],
    scores: [0, 1, 2, 3],
  },
  
  {
    id: 2,
    text: "What percentage of your revenue is recurring?",
    options: ["0-20%", "21-40%", "41-60%", "61-80%", ">80%"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 3,
    text: "What's your company's annual revenue?",
    options: ["<$5 million", "$5-20 million", "$20-50 million", "$50-100 million", ">$100 million"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 4,
    text: "What's your company's EBITDA margin?",
    options: ["<5%", "5-10%", "11-20%", ">20%"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 5,
    text: "How diversified is your client base?",
    options: ["Single client", "2-5 major clients", "6-10 major clients", "Well diversified"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 6,
    text: "What's your company's market share in its primary market?",
    options: ["<5%", "5-10%", "11-20%", "21-30%", ">30%"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 7,
    text: "How would you rate your company's brand recognition?",
    options: ["Unknown", "Some recognition", "Well-known in niche", "Industry leader"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 8,
    text: "How mature is your product/service offering?",
    options: ["In development", "Early stage", "Established", "Market-leading", "Disruptive"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 9,
    text: "How would you describe your company's growth rate compared to the industry average?",
    options: ["Below average", "Average", "Above average", "Far exceeds average"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 10,
    text: "How stable is your management team?",
    options: ["High turnover", "Some key positions unstable", "Mostly stable", "Very stable with succession plans"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 11,
    text: "How well-documented are your company's processes and procedures?",
    options: ["Not documented", "Partially documented", "Mostly documented", "Fully documented and regularly updated"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 12,
    text: "How would you rate your company's technology infrastructure?",
    options: ["Outdated", "Functional but needs upgrading", "Modern and adequate", "Cutting-edge"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 13,
    text: "How effective is your company's financial reporting and controls?",
    options: ["Basic bookkeeping", "Regular unaudited financials", "Annual audited financials", "Quarterly audited financials with strong controls"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 14,
    text: "How well-developed is your company's sales and marketing function?",
    options: ["Ad-hoc efforts", "Basic systems in place", "Well-developed function", "Highly effective with measurable ROI"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 15,
    text: "How would you describe your company's customer satisfaction and retention rates?",
    options: ["Poor", "Average", "Good", "Excellent", "Industry-leading"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 16,
    text: "How scalable is your business model?",
    options: ["Not scalable", "Scalable with significant investment", "Moderately scalable", "Highly scalable"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 17,
    text: "How well-protected is your company's intellectual property?",
    options: ["No IP protection", "Some IP protected", "Most key IP protected", "Comprehensive IP protection strategy"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 18,
    text: "How would you rate your company's ability to attract and retain top talent?",
    options: ["Struggling", "Average", "Above average", "Industry leader in talent acquisition"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 19,
    text: "How well does your company adapt to market changes and new technologies?",
    options: ["Slow to adapt", "Reactive adaptation", "Proactive adaptation", "Industry trendsetter"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 20,
    text: "How strong are your company's strategic partnerships and alliances?",
    options: ["No significant partnerships", "Some partnerships, limited value", "Strong partnerships in key areas", "Extensive high-value partnership network"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 21,
    text: "How would you rate your company's operational efficiency?",
    options: ["Poor", "Average", "Good", "Excellent", "Best-in-class"],
    scores: [0, 1, 2, 3, 4],
  },
  {
    id: 22,
    text: "How effective is your company's risk management strategy?",
    options: ["No formal strategy", "Basic risk awareness", "Comprehensive strategy", "Industry-leading risk management"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 23,
    text: "How would you describe your company's corporate governance practices?",
    options: ["Minimal", "Basic compliance", "Well-developed", "Best practice governance"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 24,
    text: "How strong is your company's competitive advantage?",
    options: ["No clear advantage", "Some advantages", "Strong in niche", "Dominant market position"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 25,
    text: "How well-prepared is your company for economic downturns?",
    options: ["Unprepared", "Some contingency plans", "Well-prepared", "Robust downturn strategy"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 26,
    text: "How would you rate your company's cash flow management?",
    options: ["Poor", "Adequate", "Good", "Excellent"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 27,
    text: "How well-developed is your company's ESG (Environmental, Social, Governance) strategy?",
    options: ["No strategy", "Basic considerations", "Developed strategy", "Industry-leading ESG practices"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 28,
    text: "How prepared is your management team for due diligence?",
    options: ["Unprepared", "Somewhat prepared", "Well-prepared", "Fully prepared with organized documentation"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 29,
    text: "How would you rate your company's innovation pipeline?",
    options: ["No formal innovation process", "Some innovation efforts", "Strong innovation pipeline", "Disruptive innovator in the industry"],
    scores: [0, 1, 2, 3],
  },
  {
    id: 30,
    text: "How aligned are your shareholders with the company's exit strategy?",
    options: ["Not aligned", "Somewhat aligned", "Mostly aligned", "Fully aligned"],
    scores: [0, 1, 2, 3],
  },
];

const detailedRecommendations = {
 "Focus on improving core financial metrics": {
    title: "Improving Core Financial Metrics",
    steps: [
      "Analyze your revenue streams and identify opportunities to increase recurring revenue",
      "Implement cost optimization strategies to improve EBITDA margin",
      "Develop KPIs for each department that align with overall financial goals",
      "Establish a regular financial review process with key stakeholders",
      "Consider implementing a robust financial forecasting model"
    ]
  },
  "Develop strategies to diversify your client base": {
    title: "Client Base Diversification Strategy",
    steps: [
      "Conduct a market segmentation analysis to identify new potential client groups",
      "Develop targeted marketing campaigns for each identified segment",
      "Explore partnerships or alliances to access new client pools",
      "Invest in developing new service offerings that appeal to a broader client base",
      "Implement a key account management program to reduce dependency on major clients"
    ]
  },
  "Implement robust processes and governance structures": {
    title: "Enhancing Processes and Governance",
    steps: [
      "Conduct a comprehensive audit of current processes and identify gaps",
      "Develop and document standard operating procedures for key business functions",
      "Establish a formal board of directors or advisory board",
      "Implement regular governance reviews and updates",
      "Invest in process automation tools to increase efficiency and consistency"
    ]
  },
  "Invest in technology infrastructure and operational efficiency": {
    title: "Technology and Operational Efficiency Roadmap",
    steps: [
      "Perform a technology stack assessment and identify areas for improvement",
      "Develop a phased technology upgrade plan aligned with business goals",
      "Implement productivity tracking tools to measure and improve operational efficiency",
      "Consider adopting AI and machine learning solutions for relevant business processes",
      "Establish a continuous improvement program for operational processes"
    ]
  },
  "Work on increasing market share and brand recognition": {
    title: "Market Share and Brand Recognition Strategy",
    steps: [
      "Conduct a comprehensive competitive analysis",
      "Develop a unique value proposition that differentiates your brand",
      "Invest in targeted digital marketing campaigns",
      "Pursue speaking engagements and thought leadership opportunities in your industry",
      "Consider strategic partnerships or acquisitions to rapidly expand market presence"
    ]
  },
  "Enhance your product/service offering": {
    title: "Product/Service Enhancement Plan",
    steps: [
      "Gather and analyze customer feedback on current offerings",
      "Conduct market research to identify emerging trends and unmet needs",
      "Develop a product/service roadmap aligned with market demands",
      "Invest in R&D to develop innovative features or entirely new offerings",
      "Implement a continuous improvement process for existing products/services"
    ]
  },
  "Strengthen your management team": {
    title: "Management Team Development Strategy",
    steps: [
      "Assess current management team skills and identify gaps",
      "Develop individualized professional development plans for key team members",
      "Implement a formal succession planning process",
      "Consider bringing in experienced executives or board members to provide additional expertise",
      "Establish a mentorship program to nurture emerging leaders within the organization"
    ]
  },
  "Improve financial reporting and controls": {
    title: "Financial Reporting and Control Enhancement",
    steps: [
      "Implement a robust ERP system if not already in place",
      "Establish a formal internal audit function",
      "Develop comprehensive financial policies and procedures",
      "Implement regular financial health checks and stress tests",
      "Consider engaging external auditors to provide additional credibility to financial reports"
    ]
  },
  "Refine your exit strategy": {
    title: "Exit Strategy Refinement Framework",
    steps: [
      "Clearly define your personal and business objectives for the exit",
      "Analyze different exit options (e.g., strategic sale, management buyout, IPO) and their implications",
      "Conduct a comprehensive company valuation",
      "Identify and prioritize potential acquirers or investors",
      "Develop a detailed timeline for exit preparation and execution"
    ]
  },
  "Prepare comprehensive documentation": {
    title: "Due Diligence Documentation Preparation",
    steps: [
      "Compile and organize all legal documents (contracts, licenses, patents)",
      "Prepare detailed financial statements and projections",
      "Document all business processes and operational procedures",
      "Gather and organize human resources documentation",
      "Prepare a comprehensive information memorandum highlighting the company's value proposition"
    ]
  },
  "Continue to innovate": {
    title: "Innovation Maintenance Strategy",
    steps: [
      "Establish a formal innovation program or R&D department",
      "Allocate a specific budget for innovation and new product/service development",
      "Implement an idea management system to capture and evaluate employee and customer ideas",
      "Foster a culture of innovation through rewards and recognition",
      "Consider partnerships with universities or research institutions for cutting-edge developments"
    ]
  },
  "Maintain your strong market position": {
    title: "Market Position Reinforcement Plan",
    steps: [
      "Regularly conduct market and competitor analysis",
      "Invest in customer retention programs to maintain loyalty",
      "Continue to evolve your unique value proposition",
      "Pursue strategic partnerships or acquisitions to strengthen market position",
      "Invest in brand building activities to maintain top-of-mind awareness"
    ]
  }
};

const ProgressBar = ({ current, total }) => {
  const percentage = ((current + 1) / total) * 100;
  return (
    <div className="relative w-full bg-gray-300 h-3 rounded-full">
      <div
        className="absolute top-0 left-0 h-3 bg-blue-600 rounded-full transition-all duration-500"
        style={{ width: `${percentage}%` }}
      />
      <p className="text-center mt-1 text-sm font-semibold text-gray-800">
        {current + 1} / {total}
      </p>
    </div>
  );
};

const Question = ({ question, onAnswer }) => (
  <div className="mb-8 p-6 rounded-lg bg-white shadow-md">
    <h3 className="text-lg font-semibold text-gray-900 mb-4">{question.text}</h3>
    <div className="flex flex-col space-y-3">
      {question.options.map((option, index) => (
        <button
          key={index}
          onClick={() => onAnswer(question.id, question.scores[index])}
          className="w-full px-4 py-2 bg-blue-500 text-white font-medium rounded-lg shadow-md hover:bg-blue-700 transition-colors"
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
    <div className="mt-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-4 py-2 bg-gray-100 text-left text-gray-700 rounded-lg hover:bg-gray-200"
      >
        <span>{recommendation}</span>
        {isOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
      </button>
      {isOpen && detail && (
        <div className="p-4 mt-2 bg-gray-50 rounded-lg shadow-inner">
          <h4 className="font-semibold mb-2">{detail.title}</h4>
          <ul className="list-disc pl-5">
            {detail.steps.map((step, index) => (
              <li key={index} className="mb-2">{step}</li>
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

  // Calculate the total score
  const { score } = useMemo(() => {
    const totalScore = Object.values(answers).reduce((a, b) => a + b, 0);
    const maxScore = questions.reduce(
      (total, question) => total + Math.max(...question.scores),
      0
    );
    return {
      score: (totalScore / maxScore) * 100,
    };
  }, [answers]);

  // Recommendations logic based on score
  const getRecommendations = useMemo(() => {
    if (score <= 40) {
      return [
        "Focus on improving core financial metrics",
        "Develop strategies to diversify your client base",
        "Implement robust processes and governance structures",
        "Invest in technology infrastructure and operational efficiency"
      ];
    }
    if (score <= 70) {
      return [
        "Work on increasing market share and brand recognition",
        "Enhance your product/service offering",
        "Strengthen your management team",
        "Improve financial reporting and controls"
      ];
    }
    return [
      "Refine your exit strategy",
      "Prepare comprehensive documentation",
      "Continue to innovate",
      "Maintain your strong market position"
    ];
  }, [score]);

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
    <div className="max-w-4xl mx-auto p-6 bg-gray-100 min-h-screen">
      <h1 className="text-3xl font-bold text-center mb-8 text-gray-800">
        Exit Readiness Assessment
      </h1>
      {!showResults ? (
        <>
          <ProgressBar current={currentQuestion} total={questions.length} />
          <Question
            question={questions[currentQuestion]}
            onAnswer={handleAnswer}
          />
        </>
      ) : (
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-2xl font-bold mb-4">
            Your Exit Readiness Score: {score.toFixed(1)} / 100
          </h2>
          <p className="mb-6">
            {score <= 40 ? (
              <><AlertCircle className="inline mr-2 text-red-600" /> Significant improvements needed for an exit.</>
            ) : score <= 70 ? (
              <><Info className="inline mr-2 text-blue-600" /> On the right track, but there's room for improvement.</>
            ) : (
              <><CheckCircle className="inline mr-2 text-green-600" /> You're well-prepared for a potential exit!</>
            )}
          </p>
          <h3 className="text-xl font-semibold mb-4">Recommendations:</h3>
          <div className="space-y-3">
            {getRecommendations.map((rec, index) => (
              <RecommendationDetail key={index} recommendation={rec} />
            ))}
          </div>
          <div className="mt-8 flex justify-center space-x-4">
            <button
              onClick={handleRetake}
              className="px-6 py-2 bg-blue-600 text-white font-semibold rounded-lg shadow-md hover:bg-blue-700"
            >
              Retake Assessment
            </button>
            {score > 70 && (
              <button
                onClick={handleEquiteqAdvice}
                className="px-6 py-2 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700"
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
