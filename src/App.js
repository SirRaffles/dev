import React, { useState, useEffect } from 'react';
import {
  ChevronRight,
  ChevronLeft,
  Target,
  TrendingUp,
  Users,
  Briefcase,
  CheckCircle,
  DollarSign,
  Zap,
  Award,
  Globe,
  Shield,
  Sun,
  Moon,
  Menu,
  X,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

const SECAccountPlanning = () => {
  const [currentSection, setCurrentSection] = useState(0);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [expandedSections, setExpandedSections] = useState([0]); // Start with first section expanded
  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Initialize from localStorage or system preference
    const saved = localStorage.getItem('theme');
    if (saved) return saved === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  // Theme persistence
  useEffect(() => {
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  // Toggle section expansion in sidebar
  const toggleSectionExpansion = (sectionIndex) => {
    if (expandedSections.includes(sectionIndex)) {
      setExpandedSections(expandedSections.filter(idx => idx !== sectionIndex));
    } else {
      setExpandedSections([...expandedSections, sectionIndex]);
    }
  };

  // Navigate to section/slide and ensure section is expanded
  const navigateToSlide = (sectionIndex, slideIndex) => {
    setCurrentSection(sectionIndex);
    setCurrentSlide(slideIndex);
    if (!expandedSections.includes(sectionIndex)) {
      setExpandedSections([...expandedSections, sectionIndex]);
    }
  };

  // Logo Components
  const IFSLogo = () => (
    <div className="flex items-center space-x-3">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="24" cy="24" r="22" fill="#6f2c91"/>
        <path d="M16 14 L24 24 L16 34 M24 14 L32 24 L24 34" stroke="white" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
      <span className="text-2xl font-bold text-gray-900">IFS</span>
    </div>
  );

  const SECLogo = () => (
    <div className="flex items-center space-x-3">
      <img
        src="https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Logo_Saudi_Electric_Company.svg/320px-Logo_Saudi_Electric_Company.svg.png"
        alt="Saudi Electricity Company"
        className="h-12 w-auto object-contain"
        onError={(e) => {
          // Fallback to text if image fails to load
          e.target.style.display = 'none';
          e.target.nextSibling.style.display = 'block';
        }}
      />
      <span className="text-xl font-bold text-gray-900 hidden">SEC</span>
    </div>
  );

  const sections = [
    {
      title: "Executive Summary",
      icon: Target,
      color: "#6f2c91",
      slides: [
        {
          title: "Saudi Electricity Company",
          subtitle: "Strategic Account Plan - IFS Digital Transformation",
          content: (
            <div className="space-y-8">
              <div className="grid grid-cols-3 gap-6">
                <div className="bg-white border border-gray-200 rounded-xl p-8 text-center shadow-sm hover:shadow-md transition-shadow">
                  <Users className="mx-auto mb-4 text-purple-700" size={40} />
                  <div className="text-4xl font-bold text-gray-900 mb-2">11.2M</div>
                  <div className="text-sm text-gray-600 font-medium">Customers Served</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl p-8 text-center shadow-sm hover:shadow-md transition-shadow">
                  <Zap className="mx-auto mb-4 text-purple-700" size={40} />
                  <div className="text-4xl font-bold text-gray-900 mb-2">70.7 GW</div>
                  <div className="text-sm text-gray-600 font-medium">Peak Load 2023</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl p-8 text-center shadow-sm hover:shadow-md transition-shadow">
                  <DollarSign className="mx-auto mb-4 text-purple-700" size={40} />
                  <div className="text-4xl font-bold text-gray-900 mb-2">$133B</div>
                  <div className="text-sm text-gray-600 font-medium">Total Assets</div>
                </div>
              </div>
              <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-8 border border-purple-200">
                <h3 className="text-2xl font-bold mb-4 text-gray-900">Vision 2030 Alignment</h3>
                <p className="text-gray-700 leading-relaxed text-lg">
                  SEC is at the heart of Saudi Arabia's transformation - powering new cities, industries,
                  and 36 million people. Our partnership will enable SEC to achieve operational excellence,
                  drive sustainability, and deliver world-class customer service.
                </p>
              </div>
            </div>
          )
        },
        {
          title: "Market Context",
          subtitle: "Saudi Arabia's Power Market Dynamics",
          content: (
            <div className="space-y-6">
              <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
                <h3 className="text-2xl font-bold mb-6 flex items-center text-gray-900">
                  <Globe className="mr-3 text-purple-700" size={28} /> Market Size &amp; Growth
                </h3>
                <ul className="space-y-4">
                  <li className="flex items-start">
                    <ChevronRight className="mr-3 mt-1 flex-shrink-0 text-purple-700" size={20} />
                    <span className="text-gray-700 text-lg">$81.7B market value (2024) with steady growth trajectory</span>
                  </li>
                  <li className="flex items-start">
                    <ChevronRight className="mr-3 mt-1 flex-shrink-0 text-purple-700" size={20} />
                    <span className="text-gray-700 text-lg">5% annual demand growth driven by Vision 2030 initiatives</span>
                  </li>
                  <li className="flex items-start">
                    <ChevronRight className="mr-3 mt-1 flex-shrink-0 text-purple-700" size={20} />
                    <span className="text-gray-700 text-lg">Record peak load of 70,663 MW in 2023 (8.2% YoY increase)</span>
                  </li>
                  <li className="flex items-start">
                    <ChevronRight className="mr-3 mt-1 flex-shrink-0 text-purple-700" size={20} />
                    <span className="text-gray-700 text-lg">MENA electricity demand projected to rise 50% by 2035</span>
                  </li>
                </ul>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
                <h3 className="text-2xl font-bold mb-4 text-gray-900">Regulatory Framework</h3>
                <p className="text-gray-700 leading-relaxed text-lg">
                  SEC operates under a regulated asset base (RAB) model with 6.65% allowed WACC (2024-26),
                  ensuring cost recovery and sustainable returns while meeting strict reliability and service quality standards.
                </p>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "Strategic Imperatives",
      icon: TrendingUp,
      color: "#8b3aa7",
      slides: [
        {
          title: "Industry Mega-Trends",
          subtitle: "Transforming the Utility Landscape",
          content: (
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-white border-l-4 border-green-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-green-700 text-lg">🌱 Decarbonization &amp; Energy Transition</h4>
                <p className="text-gray-700">
                  50% renewables by 2030, net-zero by 2050. $1.74T invested in clean energy globally in 2023.
                </p>
              </div>
              <div className="bg-white border-l-4 border-blue-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-blue-700 text-lg">⚡ Digital Grid &amp; Smart Networks</h4>
                <p className="text-gray-700">
                  23x growth in connected energy devices (2011-2021). AI-driven predictive maintenance and grid automation.
                </p>
              </div>
              <div className="bg-white border-l-4 border-yellow-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-yellow-700 text-lg">🔋 Distributed Energy Resources</h4>
                <p className="text-gray-700">
                  Rise of prosumers, rooftop solar, battery storage requiring two-way energy flow management.
                </p>
              </div>
              <div className="bg-white border-l-4 border-purple-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-purple-700 text-lg">🚗 Electrification of Transport</h4>
                <p className="text-gray-700">
                  EVs reached 15% of global sales in 2023. Saudi targets 30% EV penetration in Riyadh by 2030.
                </p>
              </div>
              <div className="bg-white border-l-4 border-orange-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-orange-700 text-lg">🎯 Customer-Centric Innovation</h4>
                <p className="text-gray-700">
                  Seamless digital engagement, personalized services. SEC achieved 81% customer satisfaction in 2023.
                </p>
              </div>
              <div className="bg-white border-l-4 border-red-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-red-700 text-lg">🛡️ Grid Resilience &amp; Cybersecurity</h4>
                <p className="text-gray-700">
                  Hardening infrastructure against extreme weather and cyber threats. SEC maintains zero data breaches.
                </p>
              </div>
            </div>
          )
        },
        {
          title: "Strategic Change Imperatives",
          subtitle: "SEC's Transformation Journey",
          content: (
            <div className="space-y-4">
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold text-red-600 bg-red-50 px-4 py-2 rounded-lg">FROM: Carbon-intensive generation</span>
                  <ChevronRight size={24} className="text-purple-700" />
                  <span className="text-sm font-semibold text-green-600 bg-green-50 px-4 py-2 rounded-lg">TO: 50% renewable &amp; 50% gas by 2030</span>
                </div>
                <p className="text-sm text-gray-600">KPI: Renewables 0% → 50%, Liquid fuel eliminated by 2030, Net-zero by 2050</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold text-red-600 bg-red-50 px-4 py-2 rounded-lg">FROM: Reactive maintenance</span>
                  <ChevronRight size={24} className="text-purple-700" />
                  <span className="text-sm font-semibold text-green-600 bg-green-50 px-4 py-2 rounded-lg">TO: Predictive, condition-based</span>
                </div>
                <p className="text-sm text-gray-600">KPI: 30-50% reduction in unplanned outages, &gt;90% equipment effectiveness</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold text-red-600 bg-red-50 px-4 py-2 rounded-lg">FROM: Siloed, manual processes</span>
                  <ChevronRight size={24} className="text-purple-700" />
                  <span className="text-sm font-semibold text-green-600 bg-green-50 px-4 py-2 rounded-lg">TO: Integrated digital operations</span>
                </div>
                <p className="text-sm text-gray-600">KPI: 30-40% faster process cycles, single source of truth, digital maturity 4.5/5</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold text-red-600 bg-red-50 px-4 py-2 rounded-lg">FROM: Commodity supplier mindset</span>
                  <ChevronRight size={24} className="text-purple-700" />
                  <span className="text-sm font-semibold text-green-600 bg-green-50 px-4 py-2 rounded-lg">TO: Customer-centric services</span>
                </div>
                <p className="text-sm text-gray-600">KPI: Customer satisfaction 81% → &gt;90%, First-contact resolution &gt;85%</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold text-red-600 bg-red-50 px-4 py-2 rounded-lg">FROM: State-dependent financials</span>
                  <ChevronRight size={24} className="text-purple-700" />
                  <span className="text-sm font-semibold text-green-600 bg-green-50 px-4 py-2 rounded-lg">TO: Commercially sustainable</span>
                </div>
                <p className="text-sm text-gray-600">KPI: EBITDA margin ~30%, Gov subsidy &lt;2%, Investment-grade credit maintained</p>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "Stakeholder Landscape",
      icon: Users,
      color: "#a347bd",
      slides: [
        {
          title: "Executive Leadership",
          subtitle: "Key Decision Makers",
          content: (
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-blue-700 text-lg">CEO - Eng. Khaled Al-Gnoon</h4>
                <p className="text-sm text-gray-700 mb-3"><strong>Focus:</strong> Vision 2030 delivery, financial sustainability, reliability</p>
                <p className="text-sm text-gray-600"><strong>Pain Points:</strong> Balancing SAR 500B capex with debt management, avoiding major outages, driving transformation</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-green-700 text-lg">CFO / SVP Finance</h4>
                <p className="text-sm text-gray-700 mb-3"><strong>Focus:</strong> Capital efficiency, cost control, credit rating maintenance</p>
                <p className="text-sm text-gray-600"><strong>Pain Points:</strong> Managing SAR 45B annual capex, optimizing O&amp;M, RAB model compliance</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-purple-700 text-lg">COO / EVP Operations</h4>
                <p className="text-sm text-gray-700 mb-3"><strong>Focus:</strong> Reliability, operational efficiency, safety excellence</p>
                <p className="text-sm text-gray-600"><strong>Pain Points:</strong> Coordination across divisions, minimizing SAIDI/SAIFI, workforce optimization</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-yellow-700 text-lg">CIO / Chief Digital Officer</h4>
                <p className="text-sm text-gray-700 mb-3"><strong>Focus:</strong> Digital transformation, system modernization, cybersecurity</p>
                <p className="text-sm text-gray-600"><strong>Pain Points:</strong> Heterogeneous systems, data silos, managing SAP/Oracle upgrades</p>
              </div>
            </div>
          )
        },
        {
          title: "Operational Leaders",
          subtitle: "Business Unit Executives",
          content: (
            <div className="space-y-4">
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <Zap className="mr-3 text-yellow-500" size={24} />
                  EVP Generation
                </h4>
                <p className="text-gray-700 mb-2"><strong>Challenge:</strong> Maximize plant reliability, minimize forced outages, optimize fuel efficiency</p>
                <p className="text-sm text-gray-600"><strong>IFS Value:</strong> Predictive maintenance to prevent unplanned downtime, integrated project management for overhauls</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <Zap className="mr-3 text-blue-500" size={24} />
                  EVP Transmission (National Grid SA)
                </h4>
                <p className="text-gray-700 mb-2"><strong>Challenge:</strong> Resilient grid expansion, managing 84,000 km of lines, renewable integration</p>
                <p className="text-sm text-gray-600"><strong>IFS Value:</strong> Linear asset management, GIS integration, predictive analytics for grid assets</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <Users className="mr-3 text-green-500" size={24} />
                  EVP Distribution &amp; Customer Services
                </h4>
                <p className="text-gray-700 mb-2"><strong>Challenge:</strong> Faster outage restoration, customer satisfaction &gt;90%, efficient new connections</p>
                <p className="text-sm text-gray-600"><strong>IFS Value:</strong> FSM optimization, mobile workforce, proactive customer communications</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <Target className="mr-3 text-purple-500" size={24} />
                  VP Asset Management
                </h4>
                <p className="text-gray-700 mb-2"><strong>Challenge:</strong> Shift from reactive to predictive maintenance, spare parts optimization</p>
                <p className="text-sm text-gray-600"><strong>IFS Value:</strong> Comprehensive EAM, IoT/AI integration, condition-based maintenance strategies</p>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "IFS Solution Portfolio",
      icon: Briefcase,
      color: "#6f2c91",
      slides: [
        {
          title: "Comprehensive Use Cases",
          subtitle: "Addressing SEC's Critical Needs",
          content: (
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-bold mb-2 text-gray-900">🔮 Predictive Maintenance for Power Plants</h4>
                <p className="text-sm text-gray-700 mb-3">IoT sensors + ML to predict equipment failures before unplanned outages</p>
                <div className="text-sm text-green-700 font-semibold bg-green-50 px-3 py-1 rounded">ROI: 12-24 months | 20-30% reduction in forced outages</div>
              </div>

              <div className="bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-bold mb-2 text-gray-900">⚡ Outage Management &amp; Fast Restoration</h4>
                <p className="text-sm text-gray-700 mb-3">Streamlined end-to-end outage process with optimized crew dispatch</p>
                <div className="text-sm text-green-700 font-semibold bg-green-50 px-3 py-1 rounded">ROI: 6-12 months | 15% reduction in SAIDI</div>
              </div>

              <div className="bg-gradient-to-br from-pink-50 to-pink-100 border border-pink-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-bold mb-2 text-gray-900">💰 Asset Investment Planning</h4>
                <p className="text-sm text-gray-700 mb-3">Value-driven portfolio optimization for SAR 500B capex program</p>
                <div className="text-sm text-green-700 font-semibold bg-green-50 px-3 py-1 rounded">ROI: 12-18 months | 5% capital efficiency improvement</div>
              </div>

              <div className="bg-gradient-to-br from-red-50 to-red-100 border border-red-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-bold mb-2 text-gray-900">📱 Mobile Workforce Empowerment</h4>
                <p className="text-sm text-gray-700 mb-3">Advanced mobile tools + AR support for first-time fix improvement</p>
                <div className="text-sm text-green-700 font-semibold bg-green-50 px-3 py-1 rounded">ROI: 6-12 months | 10% increase in FTF rate</div>
              </div>

              <div className="bg-gradient-to-br from-orange-50 to-orange-100 border border-orange-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-bold mb-2 text-gray-900">📦 Inventory Optimization</h4>
                <p className="text-sm text-gray-700 mb-3">Analytics-driven spare parts planning for billions in inventory</p>
                <div className="text-sm text-green-700 font-semibold bg-green-50 px-3 py-1 rounded">ROI: 12 months | 15% inventory reduction = SAR 750M freed</div>
              </div>

              <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 border border-yellow-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-bold mb-2 text-gray-900">🗺️ Linear Asset Management &amp; GIS</h4>
                <p className="text-sm text-gray-700 mb-3">Spatial integration for 84,000 km transmission network</p>
                <div className="text-sm text-green-700 font-semibold bg-green-50 px-3 py-1 rounded">ROI: 6-12 months | Faster fault location, reduced errors</div>
              </div>

              <div className="bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-bold mb-2 text-gray-900">🎯 Enterprise Project Management</h4>
                <p className="text-sm text-gray-700 mb-3">Robust PM practices for on-time, on-budget capital projects</p>
                <div className="text-sm text-green-700 font-semibold bg-green-50 px-3 py-1 rounded">ROI: 12-24 months | Reduce overruns 10% → 5%</div>
              </div>

              <div className="bg-gradient-to-br from-teal-50 to-teal-100 border border-teal-200 rounded-xl p-5 shadow-sm">
                <h4 className="font-bold mb-2 text-gray-900">😊 Customer Experience Enhancement</h4>
                <p className="text-sm text-gray-700 mb-3">Omnichannel communication, proactive outage alerts</p>
                <div className="text-sm text-green-700 font-semibold bg-green-50 px-3 py-1 rounded">ROI: 6-12 months | CSAT 81% → &gt;90%, 20% call reduction</div>
              </div>
            </div>
          )
        },
        {
          title: "IFS Competitive Advantages",
          subtitle: "Why IFS Outperforms SAP, Oracle &amp; Others",
          content: (
            <div className="space-y-4">
              <div className="bg-white border-l-4 border-blue-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <CheckCircle className="mr-3 text-blue-500" size={24} />
                  True End-to-End Integration
                </h4>
                <p className="text-gray-700">One platform covering asset, workforce, supply chain, projects, service. SAP/Oracle require multiple products + heavy integration.</p>
              </div>

              <div className="bg-white border-l-4 border-green-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <CheckCircle className="mr-3 text-green-500" size={24} />
                  Best-in-Class Scheduling (PSO)
                </h4>
                <p className="text-gray-700">AI-powered optimization consistently delivers 10-20% productivity improvements vs. competitors' basic scheduling.</p>
              </div>

              <div className="bg-white border-l-4 border-purple-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <CheckCircle className="mr-3 text-purple-500" size={24} />
                  Deep Utility Domain Expertise
                </h4>
                <p className="text-gray-700">Built for utilities with linear asset management, GIS integration, crew shift planning out-of-the-box. No heavy customization needed.</p>
              </div>

              <div className="bg-white border-l-4 border-yellow-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <CheckCircle className="mr-3 text-yellow-500" size={24} />
                  Proven ROI: 414% Over 3 Years
                </h4>
                <p className="text-gray-700">IDC study: $5.5M annual savings, 11-month payback. Includes 50% faster outage resolution, 30% lower IT complexity.</p>
              </div>

              <div className="bg-white border-l-4 border-red-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <CheckCircle className="mr-3 text-red-500" size={24} />
                  Modern UI &amp; Mobility
                </h4>
                <p className="text-gray-700">Intuitive, web-based interface with fully offline-capable mobile apps. SAP/Oracle UIs are clunky and complex by comparison.</p>
              </div>

              <div className="bg-white border-l-4 border-pink-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-lg">
                  <CheckCircle className="mr-3 text-pink-500" size={24} />
                  Local Partnership + Global Expertise
                </h4>
                <p className="text-gray-700">Strategic partnership with Saudi Business Machines (SBM) ensures strong local presence + IFS's global R&amp;D backing.</p>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "Business Case",
      icon: DollarSign,
      color: "#10a37f",
      slides: [
        {
          title: "Financial Impact",
          subtitle: "Quantified Benefits &amp; ROI",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-3 gap-6">
                <div className="bg-gradient-to-br from-green-50 to-green-100 border-2 border-green-300 rounded-xl p-8 text-center shadow-sm">
                  <div className="text-5xl font-bold text-green-700 mb-3">SAR 2B</div>
                  <div className="text-base text-gray-900 font-semibold mb-2">Annual O&amp;M Savings</div>
                  <div className="text-sm text-gray-600">10-15% reduction through optimized maintenance &amp; scheduling</div>
                </div>

                <div className="bg-gradient-to-br from-blue-50 to-blue-100 border-2 border-blue-300 rounded-xl p-8 text-center shadow-sm">
                  <div className="text-5xl font-bold text-blue-700 mb-3">SAR 2B</div>
                  <div className="text-base text-gray-900 font-semibold mb-2">Annual Capex Optimization</div>
                  <div className="text-sm text-gray-600">5% efficiency improvement on SAR 40B annual capex</div>
                </div>

                <div className="bg-gradient-to-br from-purple-50 to-purple-100 border-2 border-purple-300 rounded-xl p-8 text-center shadow-sm">
                  <div className="text-5xl font-bold text-purple-700 mb-3">SAR 750M</div>
                  <div className="text-base text-gray-900 font-semibold mb-2">Working Capital Release</div>
                  <div className="text-sm text-gray-600">15% inventory reduction one-time cash benefit</div>
                </div>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
                <h3 className="text-2xl font-bold mb-6 text-gray-900">5-Year ROI Summary</h3>
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <div className="text-gray-600 mb-2 font-medium">Total Investment</div>
                    <div className="text-3xl font-bold text-red-600 mb-1">SAR 300-400M</div>
                    <div className="text-sm text-gray-500">Software, implementation, training</div>
                  </div>
                  <div>
                    <div className="text-gray-600 mb-2 font-medium">Total Benefits (5 years)</div>
                    <div className="text-3xl font-bold text-green-600 mb-1">SAR 10B+</div>
                    <div className="text-sm text-gray-500">O&amp;M + Capex + Inventory + Productivity</div>
                  </div>
                  <div>
                    <div className="text-gray-600 mb-2 font-medium">Payback Period</div>
                    <div className="text-3xl font-bold text-yellow-600 mb-1">&lt;2 Years</div>
                    <div className="text-sm text-gray-500">Early benefits self-fund later phases</div>
                  </div>
                  <div>
                    <div className="text-gray-600 mb-2 font-medium">5-Year ROI</div>
                    <div className="text-3xl font-bold text-blue-600 mb-1">4:1+</div>
                    <div className="text-sm text-gray-500">Consistent with IDC 414% ROI finding</div>
                  </div>
                </div>
              </div>
            </div>
          )
        },
        {
          title: "Implementation Roadmap",
          subtitle: "24-Month Phased Approach",
          content: (
            <div className="space-y-4">
              <div className="bg-white border-l-4 border-blue-500 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-bold text-gray-900 text-lg">Phase 1: Foundation &amp; Quick Wins</h4>
                  <span className="text-sm font-semibold text-blue-700 bg-blue-50 px-4 py-2 rounded-lg">Months 0-6</span>
                </div>
                <p className="text-gray-700 mb-3">
                  Core platform setup, inventory optimization, basic work order management pilot
                </p>
                <div className="text-sm text-green-700 bg-green-50 px-4 py-2 rounded-lg inline-block">Deliverable: Pilot showing inventory reduction + improved maintenance backlog</div>
              </div>

              <div className="bg-white border-l-4 border-cyan-500 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-bold text-gray-900 text-lg">Phase 2: Core EAM &amp; FSM Rollout</h4>
                  <span className="text-sm font-semibold text-cyan-700 bg-cyan-50 px-4 py-2 rounded-lg">Months 7-12</span>
                </div>
                <p className="text-gray-700 mb-3">
                  Full maintenance mgmt across Gen/T/D, mobile FSM + PSO scheduling, Asset Investment Planning
                </p>
                <div className="text-sm text-green-700 bg-green-50 px-4 py-2 rounded-lg inline-block">Deliverable: 15% reduction in emergency maintenance, AIP influencing budget cycle</div>
              </div>

              <div className="bg-white border-l-4 border-teal-500 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-bold text-gray-900 text-lg">Phase 3: Advanced Capabilities</h4>
                  <span className="text-sm font-semibold text-teal-700 bg-teal-50 px-4 py-2 rounded-lg">Months 13-18</span>
                </div>
                <p className="text-gray-700 mb-3">
                  APM analytics with IoT, HSE &amp; Quality modules, proactive customer communications
                </p>
                <div className="text-sm text-green-700 bg-green-50 px-4 py-2 rounded-lg inline-block">Deliverable: Predictive maintenance demonstrating reduced downtime, CSAT improvements</div>
              </div>

              <div className="bg-white border-l-4 border-green-500 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-bold text-gray-900 text-lg">Phase 4: Stabilization &amp; Optimization</h4>
                  <span className="text-sm font-semibold text-green-700 bg-green-50 px-4 py-2 rounded-lg">Months 19-24</span>
                </div>
                <p className="text-gray-700 mb-3">
                  KPI monitoring, system fine-tuning, Center of Excellence establishment, legacy system retirement
                </p>
                <div className="text-sm text-green-700 bg-green-50 px-4 py-2 rounded-lg inline-block">Deliverable: Full stabilization, documented ROI achievement, handoff to SEC team</div>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "Proof Points &amp; SWOT",
      icon: Award,
      color: "#f59e0b",
      slides: [
        {
          title: "Proven Success Stories",
          subtitle: "Real Results from Similar Utilities",
          content: (
            <div className="space-y-4">
              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-blue-700 text-lg">🏭 European T&amp;D Utility</h4>
                <p className="text-gray-700 mb-2"><strong>Challenge:</strong> High unplanned outage rates, reactive maintenance</p>
                <p className="text-green-700 font-semibold"><strong>Result:</strong> 25% reduction in unplanned outages over 3 years using IFS predictive maintenance</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-green-700 text-lg">⚡ Colorado Springs Utilities (USA)</h4>
                <p className="text-gray-700 mb-2"><strong>Challenge:</strong> Multi-utility coordination, emergency response efficiency</p>
                <p className="text-green-700 font-semibold"><strong>Result:</strong> Improved workforce safety &amp; response with IFS, streamlined forest fire outage management</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-purple-700 text-lg">📊 IDC Independent Study</h4>
                <p className="text-gray-700 mb-2"><strong>Methodology:</strong> Analysis of IFS Cloud customers across industries</p>
                <p className="text-green-700 font-semibold"><strong>Result:</strong> Average 414% ROI over 3 years, $5.5M annual gains, 11-month payback, 50% faster issue resolution</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-yellow-700 text-lg">🔧 Australian Utility</h4>
                <p className="text-gray-700 mb-2"><strong>Challenge:</strong> Excess inventory tying up capital</p>
                <p className="text-green-700 font-semibold"><strong>Result:</strong> ~15% inventory value reduction using IFS integrated inventory planning</p>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-red-700 text-lg">🌍 Global Energy Company</h4>
                <p className="text-gray-700 mb-2"><strong>Challenge:</strong> Safety incident rates, HSE compliance</p>
                <p className="text-green-700 font-semibold"><strong>Result:</strong> 40% increase in near-miss reporting, 20% reduction in actual safety incidents using IFS HSE</p>
              </div>
            </div>
          )
        },
        {
          title: "SWOT Analysis",
          subtitle: "SEC's Strategic Position",
          content: (
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-4 text-green-700 text-xl">Strengths 💪</h4>
                <ul className="text-sm space-y-2 text-gray-700">
                  <li>• Dominant market position (100% T&amp;D, 66% generation)</li>
                  <li>• Strong government backing (81% ownership)</li>
                  <li>• Vision 2030 alignment &amp; political will</li>
                  <li>• Recent track record: 10M smart meters, 81% CSAT</li>
                  <li>• 94% Saudi workforce, skilled &amp; experienced</li>
                  <li>• Robust $133B asset base</li>
                </ul>
              </div>

              <div className="bg-gradient-to-br from-red-50 to-red-100 border border-red-200 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-4 text-red-700 text-xl">Weaknesses 🔍</h4>
                <ul className="text-sm space-y-2 text-gray-700">
                  <li>• Legacy systems &amp; siloed processes</li>
                  <li>• High debt (~SAR 297B liabilities)</li>
                  <li>• Aging asset components, reactive maintenance</li>
                  <li>• Complex organizational structure, slow decisions</li>
                  <li>• Customer service perception gaps (81% vs &gt;90% target)</li>
                  <li>• Regulatory dependency on ECRA tariff decisions</li>
                </ul>
              </div>

              <div className="bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-4 text-blue-700 text-xl">Opportunities 🚀</h4>
                <ul className="text-sm space-y-2 text-gray-700">
                  <li>• Vision 2030 investments &amp; smart grid initiatives</li>
                  <li>• 130 GW renewable integration by 2030</li>
                  <li>• Sector reform opening new market roles</li>
                  <li>• AI/IoT digitalization for efficiency &amp; service</li>
                  <li>• Mining 400+ TWh AMI data for new products</li>
                  <li>• Efficiency gains before next RAB rate reset</li>
                </ul>
              </div>

              <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 border border-yellow-200 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-4 text-yellow-700 text-xl">Threats ⚠️</h4>
                <ul className="text-sm space-y-2 text-gray-700">
                  <li>• Emerging competition from IPPs, potential retail opening</li>
                  <li>• Regulatory pressure &amp; potential rate cuts</li>
                  <li>• Technological disruption (DER, storage, microgrids)</li>
                  <li>• Rising cybersecurity risks to critical infrastructure</li>
                  <li>• Macro demand risks from slower growth or efficiency</li>
                  <li>• Climate risks: extreme weather straining infrastructure</li>
                </ul>
              </div>
            </div>
          )
        },
        {
          title: "ESG Alignment",
          subtitle: "Enabling SEC's Sustainability Journey",
          content: (
            <div className="space-y-5">
              <div className="bg-white border-l-4 border-green-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-xl">
                  <Globe className="mr-3 text-green-500" size={28} />
                  Environmental
                </h4>
                <p className="text-gray-700 mb-3">
                  <strong>SEC Goal:</strong> Net-zero by 2050, 50% renewables by 2030, eliminate liquid fuel
                </p>
                <p className="text-sm text-gray-600">
                  <strong>IFS Contribution:</strong> Track emissions data, optimize asset performance to reduce waste,
                  enable renewable integration, support ISO 14001 compliance. Better asset planning accelerates
                  inefficient plant retirement.
                </p>
              </div>

              <div className="bg-white border-l-4 border-blue-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-xl">
                  <Users className="mr-3 text-blue-500" size={28} />
                  Social
                </h4>
                <p className="text-gray-700 mb-3">
                  <strong>SEC Goal:</strong> Customer satisfaction &gt;90%, reliability excellence, safe workforce
                </p>
                <p className="text-sm text-gray-600">
                  <strong>IFS Contribution:</strong> Improve reliability (fewer outages = better quality of life),
                  proactive customer communication, enhanced safety through HSE module (20% injury reduction target),
                  digital training tools for workforce development.
                </p>
              </div>

              <div className="bg-white border-l-4 border-purple-500 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 flex items-center text-gray-900 text-xl">
                  <Shield className="mr-3 text-purple-500" size={28} />
                  Governance
                </h4>
                <p className="text-gray-700 mb-3">
                  <strong>SEC Goal:</strong> Transparency, risk management, regulatory compliance, localization
                </p>
                <p className="text-sm text-gray-600">
                  <strong>IFS Contribution:</strong> Comprehensive audit trails, segregation of duties, real-time
                  reporting to board/regulators, integrated risk management. Automated compliance tracking ensures
                  no missed requirements. Supports 70%+ local procurement tracking.
                </p>
              </div>

              <div className="bg-gradient-to-r from-green-50 to-teal-50 border border-green-200 rounded-xl p-6 text-center shadow-sm">
                <p className="text-gray-700 text-lg">
                  <strong className="text-green-700">Result:</strong> IFS serves as SEC's platform to not just meet but exceed ESG targets,
                  making sustainable operations an ingrained daily practice rather than a yearly reporting exercise.
                </p>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "Next Steps",
      icon: Target,
      color: "#ef4444",
      slides: [
        {
          title: "Engagement Strategy",
          subtitle: "Path to Partnership",
          content: (
            <div className="space-y-6">
              <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
                <h3 className="text-2xl font-bold mb-6 text-gray-900">Immediate Actions</h3>
                <div className="space-y-5">
                  <div className="flex items-start">
                    <div className="bg-blue-500 text-white rounded-full w-10 h-10 flex items-center justify-center mr-4 flex-shrink-0 font-bold text-lg">1</div>
                    <div>
                      <h4 className="font-bold text-gray-900 text-lg mb-1">Executive Briefing</h4>
                      <p className="text-gray-700">Schedule presentation with CIO/CDO and operational EVPs showcasing IFS capabilities + SEC-specific value proposition</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="bg-green-500 text-white rounded-full w-10 h-10 flex items-center justify-center mr-4 flex-shrink-0 font-bold text-lg">2</div>
                    <div>
                      <h4 className="font-bold text-gray-900 text-lg mb-1">Workshop Series</h4>
                      <p className="text-gray-700">Conduct focused workshops with key departments: Generation maintenance, Distribution ops, Asset planning, Customer service</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="bg-purple-500 text-white rounded-full w-10 h-10 flex items-center justify-center mr-4 flex-shrink-0 font-bold text-lg">3</div>
                    <div>
                      <h4 className="font-bold text-gray-900 text-lg mb-1">Reference Visits</h4>
                      <p className="text-gray-700">Arrange site visits to similar utilities using IFS (Dubai, Europe, or regional) to see system in action</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="bg-yellow-500 text-white rounded-full w-10 h-10 flex items-center justify-center mr-4 flex-shrink-0 font-bold text-lg">4</div>
                    <div>
                      <h4 className="font-bold text-gray-900 text-lg mb-1">Pilot Proposal</h4>
                      <p className="text-gray-700">Develop detailed proposal for Phase 1 pilot (6 months) in selected region/facility to demonstrate quick wins</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-xl font-bold mb-4 text-gray-900">Key Contacts</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-gray-600 text-sm font-medium">Account Executive</p>
                    <p className="font-bold text-gray-900 text-lg">Mark Marawy</p>
                  </div>
                  <div>
                    <p className="text-gray-600 text-sm font-medium">Local Partner</p>
                    <p className="font-bold text-gray-900 text-lg">Saudi Business Machines (SBM)</p>
                  </div>
                </div>
              </div>
            </div>
          )
        },
        {
          title: "Why Now? Why IFS?",
          subtitle: "The Perfect Convergence",
          content: (
            <div className="space-y-6">
              <div className="bg-gradient-to-br from-purple-50 via-blue-50 to-purple-50 border-2 border-purple-300 rounded-2xl p-10 shadow-lg">
                <h3 className="text-3xl font-bold mb-6 text-center text-gray-900">Empowering the Kingdom's Future, Today</h3>
                <p className="text-gray-700 text-center mb-8 text-lg leading-relaxed">
                  SEC's mission is evolving from keeping the lights on to driving strategic national outcomes:
                  reliability, sustainability, and service excellence.
                </p>

                <div className="grid grid-cols-2 gap-6 mb-8">
                  <div className="bg-white rounded-xl p-6 shadow-sm">
                    <h4 className="font-bold mb-3 text-green-700 text-lg">✓ Vision 2030 Alignment</h4>
                    <p className="text-sm text-gray-600">Digital transformation imperative, sustainability mandates, customer service excellence</p>
                  </div>
                  <div className="bg-white rounded-xl p-6 shadow-sm">
                    <h4 className="font-bold mb-3 text-blue-700 text-lg">✓ Market Timing</h4>
                    <p className="text-sm text-gray-600">RAB model stable, renewables ramping up, smart meter foundation in place</p>
                  </div>
                  <div className="bg-white rounded-xl p-6 shadow-sm">
                    <h4 className="font-bold mb-3 text-purple-700 text-lg">✓ Proven Technology</h4>
                    <p className="text-sm text-gray-600">IFS battle-tested with major utilities, 414% ROI validated by IDC, 97%+ renewal rate</p>
                  </div>
                  <div className="bg-white rounded-xl p-6 shadow-sm">
                    <h4 className="font-bold mb-3 text-yellow-700 text-lg">✓ Local Partnership</h4>
                    <p className="text-sm text-gray-600">SBM alliance ensures on-ground support, Arabic language, cultural alignment</p>
                  </div>
                </div>

                <div className="bg-gradient-to-r from-green-100 to-teal-100 rounded-xl p-8 text-center shadow-sm">
                  <p className="text-xl font-semibold mb-4 text-gray-800">
                    "SEC has always kept the Kingdom running"
                  </p>
                  <p className="text-2xl font-bold text-green-700 leading-relaxed">
                    Now, by digitally transforming with IFS, SEC will supercharge its operational
                    excellence and agility to not just meet the future, but create it.
                  </p>
                </div>
              </div>

              <div className="text-center bg-white border-2 border-purple-500 rounded-xl p-8 shadow-lg">
                <p className="text-3xl font-bold text-purple-700 mb-3">Let's Begin This Journey Together</p>
                <p className="text-gray-700 text-lg">IFS stands ready as your committed partner in SEC's transformation</p>
              </div>
            </div>
          )
        }
      ]
    }
  ];

  const currentSectionData = sections[currentSection];
  const currentSlideData = currentSectionData.slides[currentSlide];

  const nextSlide = () => {
    if (currentSlide < currentSectionData.slides.length - 1) {
      setCurrentSlide(currentSlide + 1);
    } else if (currentSection < sections.length - 1) {
      setCurrentSection(currentSection + 1);
      setCurrentSlide(0);
    }
  };

  const prevSlide = () => {
    if (currentSlide > 0) {
      setCurrentSlide(currentSlide - 1);
    } else if (currentSection > 0) {
      setCurrentSection(currentSection - 1);
      setCurrentSlide(sections[currentSection - 1].slides.length - 1);
    }
  };

  const goToSection = (sectionIndex) => {
    setCurrentSection(sectionIndex);
    setCurrentSlide(0);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors flex">
      {/* Sidebar Navigation */}
      <div className={`fixed left-0 top-0 h-full bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 shadow-lg transition-all duration-300 z-50 overflow-y-auto ${
        isSidebarOpen ? 'w-80' : 'w-0'
      }`}>
        <div className={`${isSidebarOpen ? 'p-6' : 'hidden'}`}>
          {/* Sidebar Header */}
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">Navigation</h2>
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Close sidebar"
            >
              <X size={20} className="text-gray-600 dark:text-gray-400" />
            </button>
          </div>

          {/* Sections and Slides */}
          <div className="space-y-2">
            {sections.map((section, sectionIdx) => {
              const Icon = section.icon;
              const isExpanded = expandedSections.includes(sectionIdx);
              const isCurrentSection = sectionIdx === currentSection;

              return (
                <div key={sectionIdx} className="rounded-lg overflow-hidden">
                  {/* Section Header */}
                  <button
                    onClick={() => toggleSectionExpansion(sectionIdx)}
                    className={`w-full flex items-center justify-between p-3 rounded-lg transition-all ${
                      isCurrentSection
                        ? 'bg-purple-50 dark:bg-purple-900/20 border-l-4'
                        : 'hover:bg-gray-50 dark:hover:bg-gray-700/50 border-l-4 border-transparent'
                    }`}
                    style={isCurrentSection ? { borderLeftColor: section.color } : {}}
                  >
                    <div className="flex items-center space-x-3 flex-1 text-left">
                      <Icon
                        size={18}
                        className={isCurrentSection ? 'text-purple-700 dark:text-purple-400' : 'text-gray-600 dark:text-gray-400'}
                        style={isCurrentSection ? { color: section.color } : {}}
                      />
                      <div className="flex-1">
                        <div className={`text-sm font-semibold ${
                          isCurrentSection
                            ? 'text-purple-700 dark:text-purple-400'
                            : 'text-gray-900 dark:text-white'
                        }`}>
                          {section.title}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {section.slides.length} slides
                        </div>
                      </div>
                    </div>
                    {isExpanded ? (
                      <ChevronUp size={16} className="text-gray-500 dark:text-gray-400" />
                    ) : (
                      <ChevronDown size={16} className="text-gray-500 dark:text-gray-400" />
                    )}
                  </button>

                  {/* Slides List */}
                  {isExpanded && (
                    <div className="mt-1 ml-4 space-y-1">
                      {section.slides.map((slide, slideIdx) => {
                        const isCurrentSlide = isCurrentSection && slideIdx === currentSlide;
                        return (
                          <button
                            key={slideIdx}
                            onClick={() => navigateToSlide(sectionIdx, slideIdx)}
                            className={`w-full flex items-center space-x-3 p-2.5 rounded-lg text-left transition-all ${
                              isCurrentSlide
                                ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 font-medium'
                                : 'hover:bg-gray-50 dark:hover:bg-gray-700/50 text-gray-700 dark:text-gray-300'
                            }`}
                          >
                            <div className={`w-1.5 h-1.5 rounded-full ${
                              isCurrentSlide ? 'bg-purple-700 dark:bg-purple-400' : 'bg-gray-300 dark:bg-gray-600'
                            }`}
                            style={isCurrentSlide ? { backgroundColor: section.color } : {}}
                            />
                            <span className="text-sm flex-1">{slide.title}</span>
                            <span className="text-xs text-gray-400 dark:text-gray-500">{slideIdx + 1}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className={`flex-1 transition-all duration-300 ${isSidebarOpen ? 'ml-80' : 'ml-0'}`}>
        {/* Header */}
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm sticky top-0 z-40">
          <div className="max-w-7xl mx-auto px-8 py-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-6">
                {/* Sidebar Toggle */}
                {!isSidebarOpen && (
                  <button
                    onClick={() => setIsSidebarOpen(true)}
                    className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 transition-colors"
                    aria-label="Open sidebar"
                  >
                    <Menu size={20} className="text-gray-700 dark:text-gray-300" />
                  </button>
                )}
                <IFSLogo />
                <div className="h-10 w-px bg-gray-300 dark:bg-gray-600"></div>
                <SECLogo />
                <div className="h-10 w-px bg-gray-300 dark:bg-gray-600"></div>
                <div>
                  <div className="text-lg font-bold text-gray-900 dark:text-white">Strategic Account Plan</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 font-medium mt-0.5">Saudi Electricity Company</div>
                </div>
              </div>
              <div className="flex items-center space-x-6">
                <div className="text-right">
                  <div className="text-sm font-semibold text-purple-700 dark:text-purple-400">
                    Section {currentSection + 1} of {sections.length}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {currentSectionData.title}
                  </div>
                </div>
                {/* Theme Toggle */}
                <button
                  onClick={() => setIsDarkMode(!isDarkMode)}
                  className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 transition-colors"
                  aria-label="Toggle theme"
                >
                  {isDarkMode ? (
                    <Sun size={20} className="text-yellow-500" />
                  ) : (
                    <Moon size={20} className="text-gray-700" />
                  )}
                </button>
              </div>
            </div>

          {/* Section Progress Bar */}
          <div className="flex items-center space-x-2">
            {sections.map((section, idx) => (
              <button
                key={idx}
                onClick={() => goToSection(idx)}
                className="flex-1 h-2 rounded-full transition-all relative group"
                style={{
                  backgroundColor: idx === currentSection ? section.color :
                                  idx < currentSection ? '#d1d5db' : '#e5e7eb'
                }}
                title={section.title}
              >
                <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 bg-gray-900 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
                  {section.title}
                </div>
              </button>
            ))}
          </div>

          {/* Slide Progress Indicator */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Slide:</span>
              {currentSectionData.slides.map((_, idx) => (
                <button
                  key={idx}
                  onClick={() => setCurrentSlide(idx)}
                  className={`h-2 rounded-full transition-all ${
                    idx === currentSlide ? 'w-8' : 'w-2'
                  }`}
                  style={{
                    backgroundColor: idx === currentSlide ? currentSectionData.color :
                                    idx < currentSlide ? (isDarkMode ? '#4b5563' : '#d1d5db') : (isDarkMode ? '#374151' : '#e5e7eb')
                  }}
                  title={`Slide ${idx + 1}`}
                />
              ))}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 font-medium">
              Slide {currentSlide + 1} of {currentSectionData.slides.length}
            </div>
          </div>
        </div>
        </div>

        {/* Main Content */}
      <div className="max-w-7xl mx-auto px-8 py-12">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden transition-colors">
          <div className="p-12">
            {/* Slide Header */}
            <div className="mb-10 pb-8 border-b-2 border-gray-200 dark:border-gray-700">
              <div className="flex items-center space-x-4 mb-4">
                {React.createElement(currentSectionData.icon, {
                  size: 40,
                  className: "text-purple-700 dark:text-purple-400",
                  style: { color: currentSectionData.color }
                })}
                <h1 className="text-4xl font-bold text-gray-900 dark:text-white">{currentSlideData.title}</h1>
              </div>
              {currentSlideData.subtitle && (
                <p className="text-xl text-gray-600 dark:text-gray-300 ml-14">{currentSlideData.subtitle}</p>
              )}
            </div>

            {/* Slide Content */}
            <div className="min-h-[500px]">
              {currentSlideData.content}
            </div>

            {/* Slide Navigation */}
            <div className="flex items-center justify-between mt-12 pt-8 border-t-2 border-gray-200 dark:border-gray-700">
              <button
                onClick={prevSlide}
                disabled={currentSection === 0 && currentSlide === 0}
                className="flex items-center space-x-2 px-6 py-3 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-all font-medium disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-gray-100 dark:disabled:hover:bg-gray-700"
              >
                <ChevronLeft size={20} />
                <span>Previous</span>
              </button>

              <div className="flex items-center space-x-3">
                {currentSectionData.slides.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={() => setCurrentSlide(idx)}
                    className={`h-2.5 rounded-full transition-all ${
                      currentSlide === idx ? 'w-10 bg-purple-700' : 'w-2.5 bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500'
                    }`}
                    style={currentSlide === idx ? { backgroundColor: currentSectionData.color } : {}}
                  />
                ))}
              </div>

              <button
                onClick={nextSlide}
                disabled={currentSection === sections.length - 1 && currentSlide === currentSectionData.slides.length - 1}
                className="flex items-center space-x-2 px-6 py-3 bg-purple-700 text-white rounded-lg hover:bg-purple-800 transition-all font-medium disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-purple-700"
                style={{ backgroundColor: currentSectionData.color }}
              >
                <span>Next</span>
                <ChevronRight size={20} />
              </button>
            </div>
          </div>
        </div>
      </div>

        {/* Footer */}
        <div className="max-w-7xl mx-auto px-8 pb-10">
          <div className="text-center text-gray-500 dark:text-gray-400 text-sm">
            <p className="font-medium">© 2024 IFS - Confidential &amp; Proprietary</p>
            <p className="mt-2">Saudi Electricity Company Strategic Account Plan</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SECAccountPlanning;
