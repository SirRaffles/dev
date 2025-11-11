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
  const [secLogoError, setSecLogoError] = useState(false);
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
      <img
        src="/ifs-logo.png"
        alt="IFS"
        className="h-12 w-auto object-contain"
      />
    </div>
  );

  const SECLogo = () => (
    <div className="flex items-center space-x-3">
      {!secLogoError ? (
        <img
          src="https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Logo_Saudi_Electric_Company.svg/320px-Logo_Saudi_Electric_Company.svg.png"
          alt="Saudi Electricity Company"
          className="h-12 w-auto object-contain"
          onError={() => setSecLogoError(true)}
        />
      ) : (
        <span className="text-xl font-bold text-gray-900 dark:text-white">SEC</span>
      )}
    </div>
  );

  // NEW ACCOUNT PLANNING FRAMEWORK - 5 Sections, 25 Slides
  const sections = [
    // ============================================================================
    // SECTION 1: STRATEGIC FOUNDATION (6 slides)
    // ============================================================================
    {
      title: "Strategic Foundation",
      icon: Target,
      color: "#6f2c91",
      slides: [
        // Slide 1: Executive Summary - ENHANCED with TCV targets
        {
          title: "Executive Summary",
          subtitle: "Strategic Account Plan - SEC Digital Transformation Partnership",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center shadow-sm hover:shadow-md transition-shadow">
                  <Target className="mx-auto mb-4 text-purple-700 dark:text-purple-400" size={40} />
                  <div className="text-4xl font-bold text-gray-900 dark:text-white mb-2">SAR 45M</div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 font-medium">3-Year TCV Target</div>
                </div>
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center shadow-sm hover:shadow-md transition-shadow">
                  <Users className="mx-auto mb-4 text-purple-700 dark:text-purple-400" size={40} />
                  <div className="text-4xl font-bold text-gray-900 dark:text-white mb-2">500+</div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 font-medium">User Licenses Y3</div>
                </div>
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center shadow-sm hover:shadow-md transition-shadow">
                  <DollarSign className="mx-auto mb-4 text-purple-700 dark:text-purple-400" size={40} />
                  <div className="text-4xl font-bold text-gray-900 dark:text-white mb-2">18 mo</div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 font-medium">Payback Period</div>
                </div>
              </div>

              <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/30 dark:to-purple-800/30 rounded-xl p-8 border border-purple-200 dark:border-purple-700">
                <h3 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">Strategic Opportunity</h3>
                <p className="text-gray-700 dark:text-gray-200 leading-relaxed text-lg mb-4">
                  Saudi Electricity Company (SEC) represents IFS's largest utility opportunity in the Middle East.
                  With SAR 500B capex planned through 2030 and critical operational challenges, SEC needs a
                  transformational EAM/ERP platform to achieve Vision 2030 objectives.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                  <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
                    <div className="text-sm font-semibold text-purple-700 dark:text-purple-400">Phase 1 (Y1)</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">SAR 12M</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Pilot + Core EAM</div>
                  </div>
                  <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
                    <div className="text-sm font-semibold text-purple-700 dark:text-purple-400">Phase 2 (Y2)</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">SAR 18M</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Full Deployment</div>
                  </div>
                  <div className="bg-white dark:bg-gray-800 rounded-lg p-4">
                    <div className="text-sm font-semibold text-purple-700 dark:text-purple-400">Phase 3 (Y3)</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">SAR 15M</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Advanced + AI</div>
                  </div>
                </div>
              </div>

              <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 p-6 rounded-r-xl">
                <div className="flex items-start">
                  <Shield className="mr-3 mt-1 flex-shrink-0 text-red-600" size={24} />
                  <div>
                    <h4 className="font-bold text-red-800 dark:text-red-300 mb-2">Priority: P0 - Strategic Account</h4>
                    <p className="text-red-700 dark:text-red-200">
                      Requires executive sponsorship (IFS VP), dedicated account team, and partner co-selling with SBM.
                      Target: Initial engagement Q1 2026, pilot contract Q2 2026.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 2: SEC Company Overview - ENHANCED
        {
          title: "Company Overview",
          subtitle: "Saudi Electricity Company - Scale & Complexity",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center shadow-sm">
                  <Users className="mx-auto mb-4 text-purple-700 dark:text-purple-400" size={40} />
                  <div className="text-4xl font-bold text-gray-900 dark:text-white mb-2">11.2M</div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 font-medium">Customers Served</div>
                </div>
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center shadow-sm">
                  <Zap className="mx-auto mb-4 text-purple-700 dark:text-purple-400" size={40} />
                  <div className="text-4xl font-bold text-gray-900 dark:text-white mb-2">70.7 GW</div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 font-medium">Peak Load 2023</div>
                </div>
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center shadow-sm">
                  <DollarSign className="mx-auto mb-4 text-purple-700 dark:text-purple-400" size={40} />
                  <div className="text-4xl font-bold text-gray-900 dark:text-white mb-2">$133B</div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 font-medium">Total Assets</div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-gray-900 dark:text-white">Financial Overview</h3>
                  <ul className="space-y-2 text-gray-700 dark:text-gray-200">
                    <li className="flex justify-between">
                      <span>Annual Revenue (2023):</span>
                      <span className="font-semibold">SAR 165B</span>
                    </li>
                    <li className="flex justify-between">
                      <span>Annual Capex:</span>
                      <span className="font-semibold">SAR 45B</span>
                    </li>
                    <li className="flex justify-between">
                      <span>O&M Costs:</span>
                      <span className="font-semibold">SAR 28B</span>
                    </li>
                    <li className="flex justify-between">
                      <span>Credit Rating:</span>
                      <span className="font-semibold">A (S&P)</span>
                    </li>
                  </ul>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-gray-900 dark:text-white">Organizational Structure</h3>
                  <ul className="space-y-2 text-gray-700 dark:text-gray-200">
                    <li className="flex justify-between">
                      <span>Employees:</span>
                      <span className="font-semibold">33,000+</span>
                    </li>
                    <li className="flex justify-between">
                      <span>Operating Regions:</span>
                      <span className="font-semibold">5 (Central, Eastern, Western, Southern, Northern)</span>
                    </li>
                    <li className="flex justify-between">
                      <span>Generation Plants:</span>
                      <span className="font-semibold">80+ facilities</span>
                    </li>
                    <li className="flex justify-between">
                      <span>Substations:</span>
                      <span className="font-semibold">600+ sites</span>
                    </li>
                  </ul>
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-xl p-6">
                <h3 className="text-xl font-bold mb-4 flex items-center text-gray-900 dark:text-white">
                  <Briefcase className="mr-3 text-blue-600 dark:text-blue-400" size={24} />
                  Current Systems Landscape
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <div className="font-semibold text-gray-800 dark:text-gray-200 mb-2">Core ERP:</div>
                    <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                      <li>• SAP ECC 6.0 (Financials, HR, Procurement)</li>
                      <li>• Limited EAM functionality</li>
                      <li>• Legacy work order system</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-gray-800 dark:text-gray-200 mb-2">Pain Points:</div>
                    <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                      <li>• Siloed data across divisions</li>
                      <li>• Manual field service processes</li>
                      <li>• No predictive maintenance</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 3: Strategic Context (from existing Industry Mega-Trends) - KEEP
        {
          title: "Strategic Context",
          subtitle: "Industry Mega-Trends Driving Transformation",
          content: (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white dark:bg-gray-800 border-l-4 border-green-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-green-700 dark:text-green-400 text-lg">🌱 Decarbonization & Energy Transition</h4>
                <p className="text-gray-700 dark:text-gray-200">
                  50% renewables by 2030, net-zero by 2050. $1.74T invested in clean energy globally in 2023.
                </p>
              </div>
              <div className="bg-white dark:bg-gray-800 border-l-4 border-blue-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-blue-700 dark:text-blue-400 text-lg">⚡ Digital Grid & Smart Networks</h4>
                <p className="text-gray-700 dark:text-gray-200">
                  23x growth in connected energy devices (2011-2021). AI-driven predictive maintenance and grid automation.
                </p>
              </div>
              <div className="bg-white dark:bg-gray-800 border-l-4 border-yellow-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-yellow-700 dark:text-yellow-400 text-lg">🔋 Distributed Energy Resources</h4>
                <p className="text-gray-700 dark:text-gray-200">
                  Rise of prosumers, rooftop solar, battery storage requiring two-way energy flow management.
                </p>
              </div>
              <div className="bg-white dark:bg-gray-800 border-l-4 border-purple-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-purple-700 dark:text-purple-400 text-lg">🚗 Electrification of Transport</h4>
                <p className="text-gray-700 dark:text-gray-200">
                  EVs reached 15% of global sales in 2023. Saudi targets 30% EV penetration in Riyadh by 2030.
                </p>
              </div>
              <div className="bg-white dark:bg-gray-800 border-l-4 border-orange-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-orange-700 dark:text-orange-400 text-lg">🎯 Customer-Centric Innovation</h4>
                <p className="text-gray-700 dark:text-gray-200">
                  Seamless digital engagement, personalized services. SEC achieved 81% customer satisfaction in 2023.
                </p>
              </div>
              <div className="bg-white dark:bg-gray-800 border-l-4 border-red-500 rounded-lg p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-red-700 dark:text-red-400 text-lg">🛡️ Grid Resilience & Cybersecurity</h4>
                <p className="text-gray-700 dark:text-gray-200">
                  Hardening infrastructure against extreme weather and cyber threats. SEC maintains zero data breaches.
                </p>
              </div>
            </div>
          )
        },

        // Slide 4: Business Pain Points (Part 1) - CREATE NEW
        {
          title: "Business Pain Points & Opportunities (Part 1)",
          subtitle: "Validated & Strong Indicators",
          content: (
            <div className="space-y-4">
              <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 rounded-r-xl p-6">
                <div className="flex items-start mb-3">
                  <div className="bg-red-500 text-white px-3 py-1 rounded-full text-xs font-bold mr-4">VALIDATED</div>
                  <div className="flex-1">
                    <h4 className="font-bold text-red-800 dark:text-red-300 text-lg mb-2">Asset Reliability Below Target</h4>
                    <p className="text-gray-700 dark:text-gray-200 mb-2">
                      Equipment availability at 88% vs. 95% target. Unplanned outages cost SAR 2.1B annually.
                    </p>
                    <div className="text-sm text-gray-600 dark:text-gray-400 italic">Source: SEC 2023 Annual Report, Operations Review</div>
                  </div>
                </div>
              </div>

              <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 rounded-r-xl p-6">
                <div className="flex items-start mb-3">
                  <div className="bg-red-500 text-white px-3 py-1 rounded-full text-xs font-bold mr-4">VALIDATED</div>
                  <div className="flex-1">
                    <h4 className="font-bold text-red-800 dark:text-red-300 text-lg mb-2">Reactive Maintenance Model</h4>
                    <p className="text-gray-700 dark:text-gray-200 mb-2">
                      65% of maintenance is corrective vs. industry best practice of 20%. No predictive maintenance capability.
                    </p>
                    <div className="text-sm text-gray-600 dark:text-gray-400 italic">Source: SEC Engineering VP Discussion, Oct 2025</div>
                  </div>
                </div>
              </div>

              <div className="bg-orange-50 dark:bg-orange-900/20 border-l-4 border-orange-500 rounded-r-xl p-6">
                <div className="flex items-start mb-3">
                  <div className="bg-orange-500 text-white px-3 py-1 rounded-full text-xs font-bold mr-4">STRONG INDICATOR</div>
                  <div className="flex-1">
                    <h4 className="font-bold text-orange-800 dark:text-orange-300 text-lg mb-2">Manual Work Order Planning</h4>
                    <p className="text-gray-700 dark:text-gray-200 mb-2">
                      Field technicians receive paper-based work orders. No mobile access to asset history or schematics.
                      Estimated 40% idle time due to information gaps.
                    </p>
                    <div className="text-sm text-gray-600 dark:text-gray-400 italic">Source: Site visit observations, field supervisor interviews</div>
                  </div>
                </div>
              </div>

              <div className="bg-orange-50 dark:bg-orange-900/20 border-l-4 border-orange-500 rounded-r-xl p-6">
                <div className="flex items-start mb-3">
                  <div className="bg-orange-500 text-white px-3 py-1 rounded-full text-xs font-bold mr-4">STRONG INDICATOR</div>
                  <div className="flex-1">
                    <h4 className="font-bold text-orange-800 dark:text-orange-300 text-lg mb-2">Disconnected Systems & Data Silos</h4>
                    <p className="text-gray-700 dark:text-gray-200 mb-2">
                      SAP ERP not integrated with operational systems. Asset data scattered across 15+ regional databases.
                      No single source of truth.
                    </p>
                    <div className="text-sm text-gray-600 dark:text-gray-400 italic">Source: CIO presentation, digital transformation roadmap</div>
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 5: Business Pain Points (Part 2) - CREATE NEW
        {
          title: "Business Pain Points & Opportunities (Part 2)",
          subtitle: "Quantified Impact & Discovery Needs",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-green-200 dark:border-green-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-green-700 dark:text-green-400">💰 Quantified Opportunities</h3>
                  <div className="space-y-3">
                    <div className="pb-3 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Reduce Unplanned Outages</div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">30% reduction = SAR 630M annual savings</div>
                    </div>
                    <div className="pb-3 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Optimize Technician Productivity</div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">25% improvement = SAR 420M savings</div>
                    </div>
                    <div className="pb-3 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Extend Asset Life</div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">15% extension = SAR 2.2B capex avoidance</div>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white">Improve Parts Inventory</div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">20% reduction = SAR 340M working capital</div>
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-yellow-200 dark:border-yellow-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-yellow-700 dark:text-yellow-400">🔍 Requires Discovery</h3>
                  <div className="space-y-3">
                    <div className="pb-3 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Field Service Utilization Rates</div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">Need data on actual vs. planned work hours</div>
                    </div>
                    <div className="pb-3 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Asset Failure Root Causes</div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">Detailed failure mode analysis required</div>
                    </div>
                    <div className="pb-3 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Change Management Readiness</div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">Organizational maturity assessment needed</div>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white">Integration Complexity</div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">Full API/system audit required</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 rounded-xl p-6">
                <h3 className="text-xl font-bold mb-3 text-purple-800 dark:text-purple-300">✅ Discovery Plan</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white mb-2">Phase 1 (Weeks 1-4)</div>
                    <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                      <li>• Executive stakeholder interviews</li>
                      <li>• System landscape audit</li>
                      <li>• Data quality assessment</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white mb-2">Phase 2 (Weeks 5-8)</div>
                    <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                      <li>• Process mapping workshops</li>
                      <li>• Field operations observation</li>
                      <li>• Technical architecture review</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white mb-2">Phase 3 (Weeks 9-12)</div>
                    <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                      <li>• Business case validation</li>
                      <li>• Proof of concept scoping</li>
                      <li>• Implementation roadmap</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 6: Stakeholder Landscape - ENHANCED from existing
        {
          title: "Stakeholder Analysis & Engagement",
          subtitle: "Key Decision Makers & Access Strategy",
          content: (
            <div className="space-y-6">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-purple-100 dark:bg-purple-900/30">
                      <th className="p-3 text-left text-purple-900 dark:text-purple-200 font-semibold">Executive</th>
                      <th className="p-3 text-left text-purple-900 dark:text-purple-200 font-semibold">Role</th>
                      <th className="p-3 text-left text-purple-900 dark:text-purple-200 font-semibold">Status</th>
                      <th className="p-3 text-left text-purple-900 dark:text-purple-200 font-semibold">Access Path</th>
                      <th className="p-3 text-left text-purple-900 dark:text-purple-200 font-semibold">Priority</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800">
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <td className="p-3 font-semibold text-gray-900 dark:text-white">CEO Khaled Al-Gnoon</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Final Approver</td>
                      <td className="p-3"><span className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded text-xs">Cold</span></td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Via Board contacts</td>
                      <td className="p-3"><span className="px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 rounded text-xs font-bold">P0</span></td>
                    </tr>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <td className="p-3 font-semibold text-gray-900 dark:text-white">EVP Operations</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Business Champion</td>
                      <td className="p-3"><span className="px-2 py-1 bg-yellow-200 dark:bg-yellow-900/30 rounded text-xs">Warm</span></td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Direct via ABM</td>
                      <td className="p-3"><span className="px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 rounded text-xs font-bold">P0</span></td>
                    </tr>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <td className="p-3 font-semibold text-gray-900 dark:text-white">CIO</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Tech Champion</td>
                      <td className="p-3"><span className="px-2 py-1 bg-green-200 dark:bg-green-900/30 rounded text-xs">Good</span></td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Direct relationship</td>
                      <td className="p-3"><span className="px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 rounded text-xs font-bold">P0</span></td>
                    </tr>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <td className="p-3 font-semibold text-gray-900 dark:text-white">CFO</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Financial Approver</td>
                      <td className="p-3"><span className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded text-xs">Cold</span></td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Via ROI workshop</td>
                      <td className="p-3"><span className="px-2 py-1 bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300 rounded text-xs font-bold">P1</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-xl p-6">
                  <h3 className="text-lg font-bold mb-3 text-green-800 dark:text-green-300">✓ Strengths</h3>
                  <ul className="space-y-2 text-gray-700 dark:text-gray-300 text-sm">
                    <li>• CIO relationship established (4+ meetings)</li>
                    <li>• Technical team engaged in architecture discussions</li>
                    <li>• Operations VP attended IFS utility webinar</li>
                  </ul>
                </div>

                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-xl p-6">
                  <h3 className="text-lg font-bold mb-3 text-red-800 dark:text-red-300">⚠️ Gaps to Address</h3>
                  <ul className="space-y-2 text-gray-700 dark:text-gray-300 text-sm">
                    <li>• No C-suite executive sponsor yet</li>
                    <li>• Limited access to CEO/CFO level</li>
                    <li>• Need champion development at EVP Operations</li>
                  </ul>
                </div>
              </div>
            </div>
          )
        }
      ]
    }

    // ============================================================================
    // SECTION 2: SOLUTION & COMMERCIAL (6 slides) - HIGH PRIORITY
    // ============================================================================
    ,{
      title: "Solution & Commercial",
      icon: Briefcase,
      color: "#6f2c91",
      slides: [
        // Slide 7: Solution Mapping Matrix - CREATE NEW (HIGH PRIORITY)
        {
          title: "Solution Mapping Matrix",
          subtitle: "Pain Points → IFS Solutions → Commercial SKUs",
          content: (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="bg-purple-700 dark:bg-purple-900 text-white">
                      <th className="p-2 text-left border border-purple-600">SEC Pain Point</th>
                      <th className="p-2 text-left border border-purple-600">Business Impact</th>
                      <th className="p-2 text-left border border-purple-600">IFS Solution</th>
                      <th className="p-2 text-left border border-purple-600">Primary SKU</th>
                      <th className="p-2 text-left border border-purple-600">Priority</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800">
                    <tr className="border-b border-gray-300 dark:border-gray-700">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Asset failures exceed target (88% vs 95%)</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">SAR 2.1B annual losses</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Predictive Maintenance with AI/ML</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400 font-mono">IC12922</td>
                      <td className="p-2"><span className="px-2 py-1 bg-red-500 text-white rounded text-xs font-bold">P0</span></td>
                    </tr>
                    <tr className="border-b border-gray-300 dark:border-gray-700">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Manual work order planning (40% idle time)</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">SAR 420M productivity loss</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Advanced Scheduling & Optimization</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400 font-mono">IC11200</td>
                      <td className="p-2"><span className="px-2 py-1 bg-red-500 text-white rounded text-xs font-bold">P0</span></td>
                    </tr>
                    <tr className="border-b border-gray-300 dark:border-gray-700">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Paper-based field service (25% repeat visits)</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">SAR 315M wasted time</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Mobile Work Order Management</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400 font-mono">IC12406</td>
                      <td className="p-2"><span className="px-2 py-1 bg-orange-500 text-white rounded text-xs font-bold">P1</span></td>
                    </tr>
                    <tr className="border-b border-gray-300 dark:border-gray-700">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Poor capex planning (20% overspend)</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">SAR 9B inefficiency</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Asset Investment Planning (Copperleaf)</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400 font-mono">COPPERLEAF</td>
                      <td className="p-2"><span className="px-2 py-1 bg-orange-500 text-white rounded text-xs font-bold">P1</span></td>
                    </tr>
                    <tr className="border-b border-gray-300 dark:border-gray-700">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Disconnected asset data (15+ databases)</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Decision delays, errors</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Asset O&M Core Platform</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400 font-mono">IC12920</td>
                      <td className="p-2"><span className="px-2 py-1 bg-red-500 text-white rounded text-xs font-bold">P0</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded-lg p-4">
                  <div className="text-2xl font-bold text-green-700 dark:text-green-400 mb-1">SAR 12.8B</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">Total Addressable Impact</div>
                </div>
                <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-300 dark:border-purple-700 rounded-lg p-4">
                  <div className="text-2xl font-bold text-purple-700 dark:text-purple-400 mb-1">5 Modules</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">Core + Advanced Components</div>
                </div>
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-300 dark:border-blue-700 rounded-lg p-4">
                  <div className="text-2xl font-bold text-blue-700 dark:text-blue-400 mb-1">3 Phases</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">24-Month Implementation</div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 8: IFS Competitive Advantages - KEEP + enhance
        {
          title: "IFS Competitive Advantages",
          subtitle: "Why IFS Wins at SEC",
          content: (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white dark:bg-gray-800 border-l-4 border-blue-500 rounded-r-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-blue-700 dark:text-blue-400 text-lg">🏆 Superior Field Service Scheduling</h4>
                <p className="text-gray-700 dark:text-gray-200 mb-2">
                  AI-powered optimization delivers 35% productivity improvement vs. manual planning.
                </p>
                <div className="text-sm text-purple-600 dark:text-purple-400 font-semibold">Proven at Dubai Electricity & Water Authority</div>
              </div>

              <div className="bg-white dark:bg-gray-800 border-l-4 border-green-500 rounded-r-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-green-700 dark:text-green-400 text-lg">🌍 GCC Utility References</h4>
                <p className="text-gray-700 dark:text-gray-200 mb-2">
                  Deployed at DEWA (Dubai), MEW (Kuwait), KAHRAMAA (Qatar) - proven in similar markets.
                </p>
                <div className="text-sm text-purple-600 dark:text-purple-400 font-semibold">Cultural & regulatory understanding</div>
              </div>

              <div className="bg-white dark:bg-gray-800 border-l-4 border-purple-500 rounded-r-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-purple-700 dark:text-purple-400 text-lg">🔗 SAP Integration Expertise</h4>
                <p className="text-gray-700 dark:text-gray-200 mb-2">
                  Positioned as complementary (not competitive) to SAP. Pre-built integration accelerators.
                </p>
                <div className="text-sm text-purple-600 dark:text-purple-400 font-semibold">Non-threatening to IT, faster deployment</div>
              </div>

              <div className="bg-white dark:bg-gray-800 border-l-4 border-yellow-500 rounded-r-xl p-6 shadow-sm">
                <h4 className="font-bold mb-3 text-yellow-700 dark:text-yellow-400 text-lg">🌱 Vision 2030 Alignment</h4>
                <p className="text-gray-700 dark:text-gray-200 mb-2">
                  ESG/sustainability embedded in platform. Supports renewable energy integration and carbon tracking.
                </p>
                <div className="text-sm text-purple-600 dark:text-purple-400 font-semibold">Strategic alignment with national goals</div>
              </div>
            </div>
          )
        },

        // Slide 9: Bill of Materials - Software Components (HIGH PRIORITY)
        {
          title: "Bill of Materials - Software Components",
          subtitle: "Detailed SKU List with Phasing & Dependencies",
          content: (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="bg-purple-700 dark:bg-purple-900 text-white">
                      <th className="p-2 text-left border">Module</th>
                      <th className="p-2 text-left border">SKU</th>
                      <th className="p-2 text-left border">License Type</th>
                      <th className="p-2 text-left border">Volume</th>
                      <th className="p-2 text-left border">Dependencies</th>
                      <th className="p-2 text-left border">Year</th>
                      <th className="p-2 text-right border">ARR (SAR)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800">
                    <tr className="border-b border-gray-300">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Asset O&M Core</td>
                      <td className="p-2 font-mono text-purple-700 dark:text-purple-400">IC12920</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Named User</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">200 users</td>
                      <td className="p-2 text-gray-600 dark:text-gray-400">None</td>
                      <td className="p-2 font-semibold">Y1</td>
                      <td className="p-2 text-right font-semibold text-gray-900 dark:text-white">2,400,000</td>
                    </tr>
                    <tr className="border-b border-gray-300">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Work Order Mobile</td>
                      <td className="p-2 font-mono text-purple-700 dark:text-purple-400">IC12406</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Named User</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">150 users</td>
                      <td className="p-2 text-gray-600 dark:text-gray-400">IC12920</td>
                      <td className="p-2 font-semibold">Y1</td>
                      <td className="p-2 text-right font-semibold text-gray-900 dark:text-white">1,200,000</td>
                    </tr>
                    <tr className="border-b border-gray-300">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Advanced Scheduling</td>
                      <td className="p-2 font-mono text-purple-700 dark:text-purple-400">IC11200</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Fixed Instance</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">1 instance</td>
                      <td className="p-2 text-gray-600 dark:text-gray-400">SCH6000</td>
                      <td className="p-2 font-semibold">Y2</td>
                      <td className="p-2 text-right font-semibold text-gray-900 dark:text-white">1,800,000</td>
                    </tr>
                    <tr className="border-b border-gray-300">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Predictive Maintenance</td>
                      <td className="p-2 font-mono text-purple-700 dark:text-purple-400">IC12922</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Asset-based</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">5,000 assets</td>
                      <td className="p-2 text-gray-600 dark:text-gray-400">IC12920</td>
                      <td className="p-2 font-semibold">Y2</td>
                      <td className="p-2 text-right font-semibold text-gray-900 dark:text-white">3,600,000</td>
                    </tr>
                    <tr className="border-b border-gray-300">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Asset Investment Planning</td>
                      <td className="p-2 font-mono text-purple-700 dark:text-purple-400">COPPERLEAF</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Enterprise</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">1 enterprise</td>
                      <td className="p-2 text-gray-600 dark:text-gray-400">IC12920</td>
                      <td className="p-2 font-semibold">Y3</td>
                      <td className="p-2 text-right font-semibold text-gray-900 dark:text-white">2,200,000</td>
                    </tr>
                    <tr className="bg-purple-50 dark:bg-purple-900/20 font-bold">
                      <td className="p-2" colspan="6">TOTAL SOFTWARE ARR (Year 3 Run-rate)</td>
                      <td className="p-2 text-right text-purple-800 dark:text-purple-300">11,200,000</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-300 dark:border-blue-700">
                  <div className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">Year 1 ARR</div>
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">SAR 3.6M</div>
                  <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Core EAM + Mobile</div>
                </div>
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 border border-green-300 dark:border-green-700">
                  <div className="text-sm font-semibold text-green-800 dark:text-green-300 mb-2">Year 2 ARR</div>
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">SAR 9.0M</div>
                  <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">+Scheduling +Predictive</div>
                </div>
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-4 border border-purple-300 dark:border-purple-700">
                  <div className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">Year 3 ARR</div>
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">SAR 11.2M</div>
                  <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">+AIP Full Platform</div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 10: Bill of Materials - Services & Commercial (HIGH PRIORITY)
        {
          title: "Bill of Materials - Services & Commercial Summary",
          subtitle: "Implementation, Change Management & Total 3-Year TCV",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-purple-800 dark:text-purple-300">Implementation Services</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-700 dark:text-gray-300">Year 1 (Pilot + Core)</span>
                      <span className="font-semibold text-gray-900 dark:text-white">SAR 7.2M</span>
                    </div>
                    <div className="flex justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-700 dark:text-gray-300">Year 2 (Full Deployment)</span>
                      <span className="font-semibold text-gray-900 dark:text-white">SAR 8.4M</span>
                    </div>
                    <div className="flex justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-700 dark:text-gray-300">Year 3 (Advanced + AIP)</span>
                      <span className="font-semibold text-gray-900 dark:text-white">SAR 3.6M</span>
                    </div>
                    <div className="flex justify-between pt-2 font-bold">
                      <span className="text-purple-800 dark:text-purple-300">Total Implementation</span>
                      <span className="text-purple-800 dark:text-purple-300">SAR 19.2M</span>
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-green-800 dark:text-green-300">Change Management & Support</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-700 dark:text-gray-300">Change Management Program</span>
                      <span className="font-semibold text-gray-900 dark:text-white">SAR 3.6M</span>
                    </div>
                    <div className="flex justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-700 dark:text-gray-300">Training (500 users)</span>
                      <span className="font-semibold text-gray-900 dark:text-white">SAR 1.8M</span>
                    </div>
                    <div className="flex justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-gray-700 dark:text-gray-300">Ongoing Support (3 years)</span>
                      <span className="font-semibold text-gray-900 dark:text-white">SAR 5.4M</span>
                    </div>
                    <div className="flex justify-between pt-2 font-bold">
                      <span className="text-green-800 dark:text-green-300">Total Services</span>
                      <span className="text-green-800 dark:text-green-300">SAR 10.8M</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-br from-purple-50 via-purple-100 to-blue-100 dark:from-purple-900/30 dark:via-purple-800/30 dark:to-blue-900/30 rounded-2xl p-8 border-2 border-purple-300 dark:border-purple-700 shadow-lg">
                <h2 className="text-3xl font-bold text-center mb-6 text-purple-900 dark:text-purple-200">3-Year Total Contract Value</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="text-center">
                    <div className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">Software ARR</div>
                    <div className="text-4xl font-bold text-purple-900 dark:text-purple-100">SAR 24M</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">(Cumulative 3 years)</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-semibold text-green-800 dark:text-green-300 mb-2">Services</div>
                    <div className="text-4xl font-bold text-green-900 dark:text-green-100">SAR 30M</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">(Implementation + Support)</div>
                  </div>
                  <div className="text-center border-l-2 border-white dark:border-purple-700">
                    <div className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">Total TCV</div>
                    <div className="text-5xl font-bold text-blue-900 dark:text-blue-100">SAR 54M</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">(3-Year Opportunity)</div>
                  </div>
                </div>
              </div>

              <div className="bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500 p-4 rounded-r-xl">
                <div className="flex items-start">
                  <DollarSign className="mr-3 mt-1 text-yellow-600" size={20} />
                  <div className="text-sm text-gray-700 dark:text-gray-300">
                    <span className="font-semibold">Note:</span> Year 3 ARR run-rate of SAR 11.2M establishes recurring revenue base.
                    Expansion potential: +200 users, additional sites, analytics modules.
                  </div>
                </div>
              </div>
            </div>
          )
        }
        ,

        // Slide 11: 3-Year Consumption Plan (HIGH PRIORITY)
        {
          title: "3-Year Consumption Plan",
          subtitle: "User Ramp, Asset Coverage & ARR Progression",
          content: (
            <div className="space-y-6">
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-purple-700 dark:bg-purple-900 text-white">
                      <th className="p-3 text-left border">Metric</th>
                      <th className="p-3 text-left border">Year 1 (Pilot + Core)</th>
                      <th className="p-3 text-left border">Year 2 (Full Deployment)</th>
                      <th className="p-3 text-left border">Year 3 (Optimization)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800">
                    <tr className="border-b border-gray-300">
                      <td className="p-3 font-semibold text-gray-900 dark:text-white">Phase</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">5 pilot locations → 50 sites</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">All 25 major substations</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">Full service territory</td>
                    </tr>
                    <tr className="border-b border-gray-300">
                      <td className="p-3 font-semibold text-gray-900 dark:text-white">Named Users</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">50 → 200 users</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">200 → 400 users</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">400 → 500 users</td>
                    </tr>
                    <tr className="border-b border-gray-300">
                      <td className="p-3 font-semibold text-gray-900 dark:text-white">Asset Coverage</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">20% (Critical assets)</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">60% (All transmission)</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">90% (Full grid)</td>
                    </tr>
                    <tr className="border-b border-gray-300">
                      <td className="p-3 font-semibold text-gray-900 dark:text-white">Modules Deployed</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">EAM Core + Mobile FSM</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">+ Scheduling + Predictive Maint</td>
                      <td className="p-3 text-gray-700 dark:text-gray-300">+ Asset Investment Planning</td>
                    </tr>
                    <tr className="border-b border-gray-300 bg-blue-50 dark:bg-blue-900/20">
                      <td className="p-3 font-bold text-blue-900 dark:text-blue-200">ARR</td>
                      <td className="p-3 font-bold text-blue-900 dark:text-blue-200">SAR 3.6M</td>
                      <td className="p-3 font-bold text-blue-900 dark:text-blue-200">SAR 9.0M</td>
                      <td className="p-3 font-bold text-blue-900 dark:text-blue-200">SAR 11.2M</td>
                    </tr>
                    <tr className="bg-green-50 dark:bg-green-900/20">
                      <td className="p-3 font-bold text-green-900 dark:text-green-200">Services</td>
                      <td className="p-3 font-bold text-green-900 dark:text-green-200">SAR 8.4M</td>
                      <td className="p-3 font-bold text-green-900 dark:text-green-200">SAR 9.0M</td>
                      <td className="p-3 font-bold text-green-900 dark:text-green-200">SAR 4.2M</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/30 dark:to-purple-800/30 rounded-xl p-6 border border-purple-300 dark:border-purple-700">
                  <h4 className="font-bold text-purple-900 dark:text-purple-200 mb-3">Q1-Q4 2026</h4>
                  <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                    <li>• Pilot: 5 critical substations</li>
                    <li>• Core EAM + Mobile rollout</li>
                    <li>• 200 users trained</li>
                    <li>• SAR 12M TCV</li>
                  </ul>
                </div>

                <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/30 dark:to-green-800/30 rounded-xl p-6 border border-green-300 dark:border-green-700">
                  <h4 className="font-bold text-green-900 dark:text-green-200 mb-3">Q1-Q4 2027</h4>
                  <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                    <li>• Expand to 25 major sites</li>
                    <li>• Add Scheduling + Predictive</li>
                    <li>• 400 users active</li>
                    <li>• SAR 18M TCV</li>
                  </ul>
                </div>

                <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-800/30 rounded-xl p-6 border border-blue-300 dark:border-blue-700">
                  <h4 className="font-bold text-blue-900 dark:text-blue-200 mb-3">Q1-Q4 2028</h4>
                  <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                    <li>• Full territory coverage</li>
                    <li>• Asset Investment Planning</li>
                    <li>• 500 users, analytics enabled</li>
                    <li>• SAR 15.4M TCV</li>
                  </ul>
                </div>
              </div>
            </div>
          )
        },

        // Slide 12: Revenue Projections & Business Case
        {
          title: "Revenue Projections & Business Case",
          subtitle: "Customer ROI + IFS Revenue Model",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded-xl p-6">
                  <h3 className="text-xl font-bold mb-4 flex items-center text-green-800 dark:text-green-300">
                    <CheckCircle className="mr-3" size={24} />
                    Customer Business Case
                  </h3>
                  <div className="space-y-3">
                    <div className="flex justify-between pb-2 border-b border-green-200 dark:border-green-700">
                      <span className="text-gray-700 dark:text-gray-300">3-Year Investment:</span>
                      <span className="font-semibold text-gray-900 dark:text-white">SAR 54M</span>
                    </div>
                    <div className="flex justify-between pb-2 border-b border-green-200 dark:border-green-700">
                      <span className="text-gray-700 dark:text-gray-300">5-Year Savings:</span>
                      <span className="font-semibold text-green-700 dark:text-green-400">SAR 3.2B</span>
                    </div>
                    <div className="flex justify-between pb-2 border-b border-green-200 dark:border-green-700">
                      <span className="text-gray-700 dark:text-gray-300">Payback Period:</span>
                      <span className="font-semibold text-gray-900 dark:text-white">18 months</span>
                    </div>
                    <div className="flex justify-between pt-2">
                      <span className="text-gray-700 dark:text-gray-300">5-Year ROI:</span>
                      <span className="font-bold text-green-700 dark:text-green-400 text-2xl">580%</span>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-green-200 dark:border-green-700">
                    <div className="text-sm font-semibold text-green-900 dark:text-green-200 mb-2">Non-Financial Benefits:</div>
                    <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                      <li>✓ Vision 2030 compliance</li>
                      <li>✓ Carbon emissions reduction (20%)</li>
                      <li>✓ Customer satisfaction improvement</li>
                    </ul>
                  </div>
                </div>

                <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-300 dark:border-purple-700 rounded-xl p-6">
                  <h3 className="text-xl font-bold mb-4 flex items-center text-purple-800 dark:text-purple-300">
                    <DollarSign className="mr-3" size={24} />
                    IFS Revenue Model
                  </h3>
                  <div className="space-y-2 mb-4">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-3">
                      <div className="text-xs font-semibold text-purple-700 dark:text-purple-400">Year 1 TCV</div>
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">SAR 12M</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">ARR: SAR 3.6M | Services: SAR 8.4M</div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-3">
                      <div className="text-xs font-semibold text-purple-700 dark:text-purple-400">Year 2 TCV</div>
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">SAR 18M</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">ARR: SAR 9.0M | Services: SAR 9.0M</div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-3">
                      <div className="text-xs font-semibold text-purple-700 dark:text-purple-400">Year 3 TCV</div>
                      <div className="text-2xl font-bold text-gray-900 dark:text-white">SAR 15.4M</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">ARR: SAR 11.2M | Services: SAR 4.2M</div>
                    </div>
                  </div>
                  <div className="bg-purple-700 dark:bg-purple-900 rounded-lg p-4 text-white">
                    <div className="text-sm font-semibold mb-1">Total 3-Year TCV</div>
                    <div className="text-4xl font-bold">SAR 45.4M</div>
                    <div className="text-xs mt-2">Year 3 ARR Run-rate: SAR 11.2M</div>
                  </div>
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 p-6 rounded-r-xl">
                <h4 className="font-bold text-blue-900 dark:text-blue-200 mb-3 text-lg">Expansion Potential (Year 4-5)</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white mb-2">User Growth</div>
                    <p className="text-gray-700 dark:text-gray-300">+200 users (500 → 700)</p>
                    <p className="text-blue-700 dark:text-blue-400 font-semibold">+SAR 2.4M ARR</p>
                  </div>
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white mb-2">Analytics Modules</div>
                    <p className="text-gray-700 dark:text-gray-300">AI/ML optimization suite</p>
                    <p className="text-blue-700 dark:text-blue-400 font-semibold">+SAR 1.8M ARR</p>
                  </div>
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white mb-2">Regional Expansion</div>
                    <p className="text-gray-700 dark:text-gray-300">Distribution network coverage</p>
                    <p className="text-blue-700 dark:text-blue-400 font-semibold">+SAR 3.2M ARR</p>
                  </div>
                </div>
              </div>
            </div>
          )
        }
      ]
    }

    // ============================================================================
    // SECTION 3: GO-TO-MARKET EXECUTION (7 slides) - HIGH PRIORITY
    // ============================================================================
    ,{
      title: "Go-to-Market Execution",
      icon: TrendingUp,
      color: "#10a37f",
      slides: [
        // Slide 13: Executive Engagement Strategy (Part 1)
        {
          title: "Executive Engagement Strategy - Access Playbook",
          subtitle: "Executive-by-Executive Access Plan",
          content: (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-green-700 dark:bg-green-900 text-white">
                      <th className="p-2 text-left">Executive</th>
                      <th className="p-2 text-left">Target Role</th>
                      <th className="p-2 text-left">Access Path</th>
                      <th className="p-2 text-left">Next Action</th>
                      <th className="p-2 text-left">Owner</th>
                      <th className="p-2 text-left">Timeline</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800">
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">CEO Khaled Al-Gnoon</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Final Approver</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Via Board member intro</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Vision 2030 strategic briefing</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">RVP MEA</td>
                      <td className="p-2 font-semibold">Q1 2026</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">EVP Operations</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Business Champion</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Direct via ABM campaign</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">ROI workshop invitation</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Account Exec</td>
                      <td className="p-2 font-semibold">Q4 2025</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">CIO</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Technical Champion</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Direct relationship</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Architecture validation session</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Solutions Architect</td>
                      <td className="p-2 font-semibold">Ongoing</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">CFO</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Financial Approver</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Via EVP Operations</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Business case presentation</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Account Exec</td>
                      <td className="p-2 font-semibold">Q1 2026</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-300 dark:border-blue-700 rounded-lg p-4">
                  <h4 className="font-bold text-blue-800 dark:text-blue-300 mb-2">Q4 2025</h4>
                  <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• Initial EVP Operations meeting</li>
                    <li>• CIO architecture workshop</li>
                    <li>• ABM campaign launch</li>
                  </ul>
                </div>
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded-lg p-4">
                  <h4 className="font-bold text-green-800 dark:text-green-300 mb-2">Q1 2026</h4>
                  <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• CEO strategic briefing</li>
                    <li>• CFO business case review</li>
                    <li>• Executive sponsor assignment</li>
                  </ul>
                </div>
                <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-300 dark:border-purple-700 rounded-lg p-4">
                  <h4 className="font-bold text-purple-800 dark:text-purple-300 mb-2">Q2 2026</h4>
                  <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• Proof of concept approval</li>
                    <li>• Executive steering committee</li>
                    <li>• Contract negotiation</li>
                  </ul>
                </div>
              </div>
            </div>
          )
        },

        // Slide 14: Executive Engagement Strategy (Part 2)
        {
          title: "Executive Communication Plan",
          subtitle: "Cadence & Delivery Model",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-lg font-bold mb-4 text-purple-800 dark:text-purple-300">CEO Engagement</h3>
                  <div className="space-y-3 text-sm">
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Frequency:</div>
                      <div className="text-gray-700 dark:text-gray-300">Quarterly strategic briefings</div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Format:</div>
                      <div className="text-gray-700 dark:text-gray-300">30-min 1:1, no sales pitch</div>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white">Topics:</div>
                      <ul className="text-gray-700 dark:text-gray-300 ml-4 mt-1 space-y-1">
                        <li>• Vision 2030 digital transformation</li>
                        <li>• Utility industry trends & insights</li>
                        <li>• GCC peer utility success stories</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-lg font-bold mb-4 text-green-800 dark:text-green-300">EVP Operations Engagement</h3>
                  <div className="space-y-3 text-sm">
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Frequency:</div>
                      <div className="text-gray-700 dark:text-gray-300">Monthly business case development</div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Format:</div>
                      <div className="text-gray-700 dark:text-gray-300">Working sessions with technical team</div>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white">Topics:</div>
                      <ul className="text-gray-700 dark:text-gray-300 ml-4 mt-1 space-y-1">
                        <li>• Pain point validation</li>
                        <li>• ROI modeling & KPI definition</li>
                        <li>• Pilot site selection</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-lg font-bold mb-4 text-blue-800 dark:text-blue-300">CIO Engagement</h3>
                  <div className="space-y-3 text-sm">
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Frequency:</div>
                      <div className="text-gray-700 dark:text-gray-300">Bi-weekly technical alignment</div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Format:</div>
                      <div className="text-gray-700 dark:text-gray-300">Architecture reviews, integration planning</div>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white">Topics:</div>
                      <ul className="text-gray-700 dark:text-gray-300 ml-4 mt-1 space-y-1">
                        <li>• SAP integration strategy</li>
                        <li>• Security & compliance review</li>
                        <li>• Cloud vs. on-premise deployment</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-lg font-bold mb-4 text-yellow-800 dark:text-yellow-300">Executive Sponsor Program</h3>
                  <div className="space-y-3 text-sm">
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">IFS Sponsor:</div>
                      <div className="text-gray-700 dark:text-gray-300">VP Utilities (IFS executive)</div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">SEC Sponsor:</div>
                      <div className="text-gray-700 dark:text-gray-300">EVP Operations (target)</div>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white">Cadence:</div>
                      <div className="text-gray-700 dark:text-gray-300">Quarterly strategic business reviews</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 15: ABM Strategy (Part 1)
        {
          title: "Account-Based Marketing Strategy",
          subtitle: "Campaign Overview & Objectives",
          content: (
            <div className="space-y-6">
              <div className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/30 dark:to-blue-900/30 rounded-xl p-6 border border-purple-200 dark:border-purple-700">
                <h3 className="text-2xl font-bold mb-4 text-purple-900 dark:text-purple-200">Campaign Objectives</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <div className="font-semibold text-purple-800 dark:text-purple-300 mb-2">Primary Goals:</div>
                    <ul className="text-gray-700 dark:text-gray-300 space-y-2">
                      <li>• Position IFS as strategic partner for Vision 2030</li>
                      <li>• Generate 5+ C-suite executive meetings</li>
                      <li>• Influence SAR 45M+ pipeline opportunity</li>
                      <li>• Establish thought leadership in utility digital transformation</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-purple-800 dark:text-purple-300 mb-2">Success Metrics:</div>
                    <ul className="text-gray-700 dark:text-gray-300 space-y-2">
                      <li>• 8+ stakeholder touchpoints per quarter</li>
                      <li>• CEO-level intro by Q1 2026</li>
                      <li>• Pilot approval by Q2 2026</li>
                      <li>• Champion identified at EVP Operations</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 shadow-sm">
                  <div className="text-purple-700 dark:text-purple-400 font-bold mb-2">Month 1-2</div>
                  <h4 className="font-semibold text-gray-900 dark:text-white mb-2">Research & Content</h4>
                  <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• Custom SEC research report</li>
                    <li>• "Saudi Utility Benchmark" study</li>
                    <li>• LinkedIn thought leadership</li>
                  </ul>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 shadow-sm">
                  <div className="text-purple-700 dark:text-purple-400 font-bold mb-2">Month 3-4</div>
                  <h4 className="font-semibold text-gray-900 dark:text-white mb-2">Engagement Events</h4>
                  <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• Executive roundtable (Dubai/Riyadh)</li>
                    <li>• Personalized ROI models</li>
                    <li>• Site visit to DEWA reference</li>
                  </ul>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 shadow-sm">
                  <div className="text-purple-700 dark:text-purple-400 font-bold mb-2">Month 5-6</div>
                  <h4 className="font-semibold text-gray-900 dark:text-white mb-2">Conversion</h4>
                  <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• Vision 2030 alignment workshop</li>
                    <li>• Proof of concept proposal</li>
                    <li>• Executive steering committee</li>
                  </ul>
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
                <div className="flex items-start">
                  <DollarSign className="mr-3 mt-1 text-blue-600" size={20} />
                  <div>
                    <div className="font-bold text-blue-900 dark:text-blue-200 mb-1">Budget: $100K over 6 months</div>
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      Allocation: 40% content creation, 30% events, 20% personalization, 10% tools & tech
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 16: ABM Strategy (Part 2) - Content Calendar
        {
          title: "ABM Content & Engagement Calendar",
          subtitle: "Touchpoint Strategy & Cadence",
          content: (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-purple-700 dark:bg-purple-900 text-white">
                      <th className="p-2 text-left">Touchpoint Type</th>
                      <th className="p-2 text-left">Frequency</th>
                      <th className="p-2 text-left">Format</th>
                      <th className="p-2 text-left">Owner</th>
                      <th className="p-2 text-left">Target Audience</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800">
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Thought Leadership</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Monthly</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">LinkedIn articles, industry reports</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Marketing</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">C-suite, VP-level</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Executive Briefings</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Quarterly</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">2-page strategic insights</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Account Exec</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">CEO, CFO, EVP Ops</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Networking Events</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Bi-annually</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Roundtables, conferences</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Regional Marketing</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Multi-stakeholder</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Personal Outreach</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Bi-weekly</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Email, LinkedIn, phone</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Account Exec</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">All key stakeholders</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded-lg p-4">
                  <h4 className="font-bold text-green-800 dark:text-green-300 mb-3">✓ Personalization Strategy</h4>
                  <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                    <li>• Custom ROI models per executive (CFO: capex efficiency, EVP Ops: reliability)</li>
                    <li>• Role-specific case studies (CEO: strategic, CIO: technical)</li>
                    <li>• Tailored messaging aligned with individual KPIs & pain points</li>
                  </ul>
                </div>

                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-300 dark:border-blue-700 rounded-lg p-4">
                  <h4 className="font-bold text-blue-800 dark:text-blue-300 mb-3">📊 Campaign Tracking</h4>
                  <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                    <li>• Email open rates, content downloads, event attendance</li>
                    <li>• LinkedIn engagement metrics per executive</li>
                    <li>• Meeting conversion rates & pipeline influence attribution</li>
                  </ul>
                </div>
              </div>
            </div>
          )
        }
        ,

        // Slide 17: Partner Engagement Strategy (Part 1) - HIGH PRIORITY
        {
          title: "Partner Engagement Strategy - Ecosystem Overview",
          subtitle: "Critical for SEC Success - Government & SBM Relationships",
          content: (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-green-700 dark:bg-green-900 text-white">
                      <th className="p-2 text-left">Partner</th>
                      <th className="p-2 text-left">Role</th>
                      <th className="p-2 text-left">Strengths</th>
                      <th className="p-2 text-left">Engagement Status</th>
                      <th className="p-2 text-left">Next Steps</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800">
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Saudi Business Machines (SBM)</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Prime Implementer</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Government relationships, local presence, 500+ consultants</td>
                      <td className="p-2"><span className="px-2 py-1 bg-green-200 dark:bg-green-900/30 rounded text-xs">MOU Signed</span></td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Joint PoC proposal Q1 2026</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">SAP</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Technology Partner</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Installed base at SEC (ECC 6.0), trust established</td>
                      <td className="p-2"><span className="px-2 py-1 bg-yellow-200 dark:bg-yellow-900/30 rounded text-xs">Informal</span></td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Integration architecture workshop</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Local Advisory Firm</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Strategy Validation</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">SEC executive relationships, business case expertise</td>
                      <td className="p-2"><span className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded text-xs">Not Engaged</span></td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Introduce for business case validation</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Copperleaf (Asset Investment Planning)</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Solution Partner</td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">AIP leader, utility expertise, IFS partnership</td>
                      <td className="p-2"><span className="px-2 py-1 bg-green-200 dark:bg-green-900/30 rounded text-xs">Partner Program</span></td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Joint capex optimization demo</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded-xl p-6">
                  <h3 className="text-lg font-bold mb-3 text-green-800 dark:text-green-300">✓ SBM Strategic Value</h3>
                  <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                    <li><span className="font-semibold">Government Access:</span> Direct relationships with Ministry of Energy, SEC Board</li>
                    <li><span className="font-semibold">Local Presence:</span> Riyadh office, Arabic-speaking consultants</li>
                    <li><span className="font-semibold">Delivery Capacity:</span> Can scale to 50+ resources for implementation</li>
                    <li><span className="font-semibold">Credibility:</span> Delivered 10+ Saudi government IT projects</li>
                  </ul>
                </div>

                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-300 dark:border-blue-700 rounded-xl p-6">
                  <h3 className="text-lg font-bold mb-3 text-blue-800 dark:text-blue-300">🤝 SAP Collaboration Strategy</h3>
                  <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                    <li><span className="font-semibold">Position:</span> "IFS complements SAP for asset-intensive operations"</li>
                    <li><span className="font-semibold">Messaging:</span> "Best-of-breed integration, not replacement"</li>
                    <li><span className="font-semibold">Technical:</span> Pre-built SAP connectors, proven integration patterns</li>
                    <li><span className="font-semibold">Benefit:</span> Reduces CIO resistance, accelerates procurement</li>
                  </ul>
                </div>
              </div>
            </div>
          )
        },

        // Slide 18: Partner Engagement Strategy (Part 2) - Go-to-Market Plan
        {
          title: "Partner Go-to-Market Plan",
          subtitle: "SBM Co-Selling & Commercial Model",
          content: (
            <div className="space-y-6">
              <div className="bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/30 dark:to-blue-900/30 rounded-xl p-6 border border-green-300 dark:border-green-700">
                <h3 className="text-2xl font-bold mb-4 text-green-900 dark:text-green-200">SBM Partnership Strategy</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <div className="font-bold text-green-800 dark:text-green-300 mb-2">Q1 2026</div>
                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                      <li>• Joint account planning session</li>
                      <li>• IFS training for 5 SBM consultants</li>
                      <li>• Co-develop discovery approach</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-bold text-green-800 dark:text-green-300 mb-2">Q2 2026</div>
                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                      <li>• Co-deliver proof of concept</li>
                      <li>• Joint presentation to SEC steering committee</li>
                      <li>• Collaborate on RFP response</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-bold text-green-800 dark:text-green-300 mb-2">Q3 2026</div>
                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                      <li>• Joint Phase 1 proposal</li>
                      <li>• SBM leads implementation</li>
                      <li>• Contract signing & kickoff</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-purple-800 dark:text-purple-300">Commercial Model</h3>
                  <div className="space-y-3 text-sm">
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Software Licenses:</div>
                      <div className="text-gray-700 dark:text-gray-300">IFS direct (SAR 24M over 3 years)</div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">Implementation Services:</div>
                      <div className="text-gray-700 dark:text-gray-300">SBM prime contractor (SAR 30M)</div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-gray-900 dark:text-white">IFS Services:</div>
                      <div className="text-gray-700 dark:text-gray-300">Architecture, PM oversight (SAR 6M)</div>
                    </div>
                    <div className="font-semibold text-purple-800 dark:text-purple-300">
                      Total 3-Year TCV: SAR 60M (IFS: SAR 30M, SBM: SAR 30M)
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-blue-800 dark:text-blue-300">Roles & Responsibilities</h3>
                  <div className="space-y-3 text-sm">
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="font-semibold text-blue-700 dark:text-blue-400">IFS Leads:</div>
                      <ul className="text-gray-700 dark:text-gray-300 ml-4 mt-1 space-y-1">
                        <li>• Executive relationships & strategy</li>
                        <li>• Solution architecture & configuration</li>
                        <li>• Product roadmap & innovation</li>
                      </ul>
                    </div>
                    <div>
                      <div className="font-semibold text-green-700 dark:text-green-400">SBM Leads:</div>
                      <ul className="text-gray-700 dark:text-gray-300 ml-4 mt-1 space-y-1">
                        <li>• On-site implementation & customization</li>
                        <li>• Change management & training</li>
                        <li>• Local support & maintenance</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500 p-4 rounded-r-xl">
                <div className="flex items-start">
                  <Shield className="mr-3 mt-1 text-yellow-600" size={20} />
                  <div className="text-sm text-gray-700 dark:text-gray-300">
                    <span className="font-semibold">Risk Mitigation:</span> SBM partnership critical for government approval.
                    Without local partner, procurement probability drops from 80% to 30%.
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 19: Competitive Landscape
        {
          title: "Competitive Landscape & Positioning",
          subtitle: "Competitive Intel & Win Strategy",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-blue-800 dark:text-blue-300">Incumbent Systems</h3>
                  <div className="space-y-3">
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white mb-1">SAP ECC 6.0</div>
                      <div className="text-sm text-gray-700 dark:text-gray-300">Financials, HR, Procurement. Limited EAM functionality.</div>
                      <div className="text-xs text-purple-600 dark:text-purple-400 mt-1 font-semibold">
                        Strategy: Position as complementary, not replacement
                      </div>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white mb-1">Homegrown FSM</div>
                      <div className="text-sm text-gray-700 dark:text-gray-300">Legacy work order system, no mobile, manual scheduling.</div>
                      <div className="text-xs text-purple-600 dark:text-purple-400 mt-1 font-semibold">
                        Strategy: Highlight modern capabilities & ROI
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-red-800 dark:text-red-300">Competitive Threats</h3>
                  <div className="space-y-3">
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white mb-1">IBM Maximo</div>
                      <div className="text-sm text-gray-700 dark:text-gray-300">Strong EAM platform, but weaker FSM & scheduling.</div>
                      <div className="text-xs text-green-600 dark:text-green-400 mt-1 font-semibold">
                        IFS Advantage: Superior mobile FSM, 35% scheduling gains
                      </div>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white mb-1">Oracle EAM / Microsoft Dynamics</div>
                      <div className="text-sm text-gray-700 dark:text-gray-300">Evaluated but lack utility-specific expertise.</div>
                      <div className="text-xs text-green-600 dark:text-green-400 mt-1 font-semibold">
                        IFS Advantage: GCC utility references, proven in region
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/30 dark:to-blue-900/30 rounded-xl p-6 border-2 border-purple-300 dark:border-purple-700">
                <h3 className="text-2xl font-bold mb-4 text-purple-900 dark:text-purple-200">Why IFS Wins at SEC</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <div className="font-semibold text-purple-800 dark:text-purple-300 mb-2">🏆 Superior Field Service Scheduling</div>
                    <p className="text-sm text-gray-700 dark:text-gray-300">AI-powered optimization delivers 35% productivity improvement vs. manual planning (proven at DEWA)</p>
                  </div>
                  <div>
                    <div className="font-semibold text-purple-800 dark:text-purple-300 mb-2">🌍 GCC Utility References</div>
                    <p className="text-sm text-gray-700 dark:text-gray-300">Deployed at Dubai, Kuwait, Qatar - proven in similar markets with cultural & regulatory understanding</p>
                  </div>
                  <div>
                    <div className="font-semibold text-purple-800 dark:text-purple-300 mb-2">🔗 SAP Integration</div>
                    <p className="text-sm text-gray-700 dark:text-gray-300">Pre-built accelerators, non-threatening positioning reduces CIO resistance</p>
                  </div>
                  <div>
                    <div className="font-semibold text-purple-800 dark:text-purple-300 mb-2">🌱 Vision 2030 Alignment</div>
                    <p className="text-sm text-gray-700 dark:text-gray-300">ESG/sustainability embedded, supports renewable integration & carbon tracking</p>
                  </div>
                </div>
              </div>
            </div>
          )
        }
      ]
    }

    // ============================================================================
    // SECTION 4: DE-RISKING & VALIDATION (4 slides)
    // ============================================================================
    ,{
      title: "De-Risking & Validation",
      icon: Shield,
      color: "#f59e0b",
      slides: [
        // Slide 20: Proof Points - KEEP from existing
        {
          title: "Proven Success Stories",
          subtitle: "Real Results from Similar Utilities",
          content: (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-blue-700 dark:text-blue-400 text-lg">🇦🇪 Dubai Electricity & Water Authority (DEWA)</h4>
                <p className="text-gray-700 dark:text-gray-200 mb-3 text-sm">
                  Implemented IFS EAM for 40,000+ assets across generation, transmission, and distribution.
                </p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                    <span className="text-xs text-gray-600 dark:text-gray-400">Asset Availability:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">+12%</span>
                  </div>
                  <div className="flex items-center justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                    <span className="text-xs text-gray-600 dark:text-gray-400">Work Order Cycle:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">-35%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-600 dark:text-gray-400">Maintenance Costs:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">-18%</span>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-green-700 dark:text-green-400 text-lg">🇰🇼 Ministry of Electricity & Water (MEW Kuwait)</h4>
                <p className="text-gray-700 dark:text-gray-200 mb-3 text-sm">
                  Deployed IFS across 6 power plants and water desalination facilities with 3,500 users.
                </p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                    <span className="text-xs text-gray-600 dark:text-gray-400">Unplanned Outages:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">-28%</span>
                  </div>
                  <div className="flex items-center justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                    <span className="text-xs text-gray-600 dark:text-gray-400">Spare Parts Inventory:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">-22%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-600 dark:text-gray-400">Technician Productivity:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">+31%</span>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <h4 className="font-bold mb-3 text-purple-700 dark:text-purple-400 text-lg">🇶🇦 KAHRAMAA (Qatar General Electricity & Water Corporation)</h4>
                <p className="text-gray-700 dark:text-gray-200 mb-3 text-sm">
                  Enterprise EAM rollout supporting World Cup 2022 infrastructure reliability goals.
                </p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                    <span className="text-xs text-gray-600 dark:text-gray-400">System Reliability:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">99.99%</span>
                  </div>
                  <div className="flex items-center justify-between pb-2 border-b border-gray-200 dark:border-gray-700">
                    <span className="text-xs text-gray-600 dark:text-gray-400">PM Compliance:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">95%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-600 dark:text-gray-400">Mobile Adoption:</span>
                    <span className="text-sm font-semibold text-green-600 dark:text-green-400">87%</span>
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 21: ESG Alignment - KEEP from existing
        {
          title: "ESG Alignment & Vision 2030",
          subtitle: "Enabling SEC's Sustainability Journey",
          content: (
            <div className="space-y-6">
              <div className="bg-gradient-to-r from-green-50 via-blue-50 to-purple-50 dark:from-green-900/30 dark:via-blue-900/30 dark:to-purple-900/30 rounded-xl p-8 border border-green-300 dark:border-green-700">
                <h3 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">Vision 2030 Strategic Alignment</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <div className="font-semibold text-green-800 dark:text-green-300 mb-2">Environmental Goals</div>
                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                      <li>✓ Support 50% renewable energy target by 2030</li>
                      <li>✓ Track carbon emissions reduction (net-zero by 2050)</li>
                      <li>✓ Optimize asset lifecycle to reduce waste</li>
                      <li>✓ Enable circular economy for spare parts</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-blue-800 dark:text-blue-300 mb-2">Social & Governance</div>
                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                      <li>✓ Improve service reliability for 11.2M customers</li>
                      <li>✓ Enhance worker safety through predictive maintenance</li>
                      <li>✓ Support Saudi workforce development & training</li>
                      <li>✓ Transparent reporting for RAB regulatory compliance</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white dark:bg-gray-800 border-l-4 border-green-500 rounded-r-xl p-4 shadow-sm">
                  <div className="text-3xl font-bold text-green-700 dark:text-green-400 mb-2">20%</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">Carbon Emissions Reduction (via predictive maintenance & efficiency)</div>
                </div>
                <div className="bg-white dark:bg-gray-800 border-l-4 border-blue-500 rounded-r-xl p-4 shadow-sm">
                  <div className="text-3xl font-bold text-blue-700 dark:text-blue-400 mb-2">30%</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">Asset Life Extension (sustainability & capex avoidance)</div>
                </div>
                <div className="bg-white dark:bg-gray-800 border-l-4 border-purple-500 rounded-r-xl p-4 shadow-sm">
                  <div className="text-3xl font-bold text-purple-700 dark:text-purple-400 mb-2">50%</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">Reduction in Paper Usage (mobile-first field operations)</div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 22: Risk Assessment - CREATE NEW
        {
          title: "Risk Assessment & Mitigation",
          subtitle: "De-Risking Strategy & Contingency Plans",
          content: (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-red-700 dark:bg-red-900 text-white">
                      <th className="p-2 text-left">Risk</th>
                      <th className="p-2 text-center">Probability</th>
                      <th className="p-2 text-center">Impact</th>
                      <th className="p-2 text-left">Mitigation Strategy</th>
                      <th className="p-2 text-left">Owner</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800">
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Budget freeze due to oil price volatility</td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-yellow-200 dark:bg-yellow-900/30 rounded text-xs">Med</span></td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-red-200 dark:bg-red-900/30 rounded text-xs">High</span></td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Align with government-backed capex programs, show Vision 2030 strategic value</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Account Exec</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">SAP resistance to third-party EAM</td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-red-200 dark:bg-red-900/30 rounded text-xs">High</span></td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-yellow-200 dark:bg-yellow-900/30 rounded text-xs">Med</span></td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">"Complementary not competitive" positioning, co-sell with SAP, integration workshops</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Solutions Architect</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Long decision cycle (24+ months typical)</td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-red-200 dark:bg-red-900/30 rounded text-xs">High</span></td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-yellow-200 dark:bg-yellow-900/30 rounded text-xs">Med</span></td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Secure pilot/PoC early (Q2 2026) to build momentum and prove value incrementally</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Account Exec</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Competitive bid requirement (govt. procurement)</td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-red-200 dark:bg-red-900/30 rounded text-xs">High</span></td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-yellow-200 dark:bg-yellow-900/30 rounded text-xs">Med</span></td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Leverage SBM relationship, differentiate early with utility references & GCC credibility</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">RVP MEA</td>
                    </tr>
                    <tr className="border-b">
                      <td className="p-2 font-semibold text-gray-900 dark:text-white">Change management resistance (cultural)</td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-yellow-200 dark:bg-yellow-900/30 rounded text-xs">Med</span></td>
                      <td className="p-2 text-center"><span className="px-2 py-1 bg-red-200 dark:bg-red-900/30 rounded text-xs">High</span></td>
                      <td className="p-2 text-gray-700 dark:text-gray-300">Dedicated change mgmt program (SAR 3.6M), pilot with early adopters, executive sponsorship</td>
                      <td className="p-2 text-purple-700 dark:text-purple-400">Delivery Team</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded-lg p-4">
                  <h4 className="font-bold text-green-800 dark:text-green-300 mb-2">✓ Strengths</h4>
                  <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• GCC utility references de-risk technical fit</li>
                    <li>• SBM partnership de-risks local execution</li>
                    <li>• CIO relationship provides internal champion</li>
                  </ul>
                </div>
                <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-300 dark:border-yellow-700 rounded-lg p-4">
                  <h4 className="font-bold text-yellow-800 dark:text-yellow-300 mb-2">⚠️ Watch List</h4>
                  <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• Oil price drops below $70/barrel</li>
                    <li>• Competitive threat from SAP (Asset Manager)</li>
                    <li>• Executive sponsor churn (promotions/departures)</li>
                  </ul>
                </div>
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-300 dark:border-blue-700 rounded-lg p-4">
                  <h4 className="font-bold text-blue-800 dark:text-blue-300 mb-2">📊 Overall Risk</h4>
                  <div className="text-2xl font-bold text-blue-700 dark:text-blue-400 mb-1">MEDIUM</div>
                  <div className="text-xs text-gray-700 dark:text-gray-300">Manageable with proactive mitigation</div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 23: SWOT Analysis - CONSOLIDATE from existing
        {
          title: "SWOT Analysis",
          subtitle: "SEC Strategic Position Assessment",
          content: (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded-xl p-6">
                <h3 className="text-xl font-bold mb-4 text-green-800 dark:text-green-300">💪 Strengths</h3>
                <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                  <li>✓ GCC utility references (DEWA, MEW, KAHRAMAA)</li>
                  <li>✓ Superior field service scheduling (35% productivity gain)</li>
                  <li>✓ SAP complementary positioning reduces resistance</li>
                  <li>✓ SBM partnership for local credibility & delivery</li>
                  <li>✓ CIO relationship & technical team engagement</li>
                  <li>✓ Vision 2030 alignment built into platform</li>
                </ul>
              </div>

              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-300 dark:border-yellow-700 rounded-xl p-6">
                <h3 className="text-xl font-bold mb-4 text-yellow-800 dark:text-yellow-300">⚠️ Weaknesses</h3>
                <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                  <li>⚠ No C-suite executive sponsor yet (CEO/CFO cold)</li>
                  <li>⚠ Limited brand awareness in Saudi Arabia vs. SAP/IBM</li>
                  <li>⚠ Higher upfront cost vs. incumbent system extensions</li>
                  <li>⚠ No direct Saudi Arabia reference (first mover risk)</li>
                  <li>⚠ Long sales cycle (24+ months typical for govt.)</li>
                </ul>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-300 dark:border-blue-700 rounded-xl p-6">
                <h3 className="text-xl font-bold mb-4 text-blue-800 dark:text-blue-300">🚀 Opportunities</h3>
                <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                  <li>✓ Vision 2030 urgency creates transformation imperative</li>
                  <li>✓ SAR 500B capex (2024-2030) requires modern EAM</li>
                  <li>✓ Asset reliability crisis (88% vs 95% target) proven pain</li>
                  <li>✓ Pilot can demonstrate ROI in 6 months (momentum)</li>
                  <li>✓ Expansion to distribution network (additional SAR 30M+)</li>
                </ul>
              </div>

              <div className="bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-700 rounded-xl p-6">
                <h3 className="text-xl font-bold mb-4 text-red-800 dark:text-red-300">⛔ Threats</h3>
                <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                  <li>⛔ Budget freeze if oil prices drop (volatile market)</li>
                  <li>⛔ SAP pushes competitive Asset Manager offering</li>
                  <li>⛔ IBM Maximo or Oracle wins via aggressive pricing</li>
                  <li>⛔ Decision delayed 12+ months (lost momentum)</li>
                  <li>⛔ Change management failure post-implementation</li>
                </ul>
              </div>
            </div>
          )
        }
      ]
    }

    // ============================================================================
    // SECTION 5: EXECUTION PLAN (2 slides)
    // ============================================================================
    ,{
      title: "Execution Plan",
      icon: CheckCircle,
      color: "#ef4444",
      slides: [
        // Slide 24: Engagement Roadmap - CONSOLIDATE from existing
        {
          title: "Engagement Roadmap & Milestones",
          subtitle: "24-Month Path to Partnership",
          content: (
            <div className="space-y-6">
              <div className="relative">
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-purple-300 dark:bg-purple-700"></div>
                
                <div className="ml-8 space-y-6">
                  {/* Q4 2025 */}
                  <div className="relative">
                    <div className="absolute -left-9 top-2 w-4 h-4 bg-purple-500 rounded-full border-4 border-white dark:border-gray-900"></div>
                    <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 rounded-xl p-6">
                      <h4 className="text-xl font-bold text-purple-900 dark:text-purple-200 mb-3">Q4 2025: Relationship & Discovery</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white mb-2">Engagement Activities:</div>
                          <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                            <li>• Week 2: Initial EVP Operations meeting</li>
                            <li>• Week 6: ABM campaign launch</li>
                            <li>• Week 10: ROI workshop with CFO/COO</li>
                            <li>• Week 12: Technical architecture session (CIO)</li>
                          </ul>
                        </div>
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white mb-2">Deliverables:</div>
                          <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                            <li>• Pain point validation report</li>
                            <li>• Preliminary business case</li>
                            <li>• System landscape assessment</li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Q1 2026 */}
                  <div className="relative">
                    <div className="absolute -left-9 top-2 w-4 h-4 bg-green-500 rounded-full border-4 border-white dark:border-gray-900"></div>
                    <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-xl p-6">
                      <h4 className="text-xl font-bold text-green-900 dark:text-green-200 mb-3">Q1 2026: Executive Access & PoC Proposal</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white mb-2">Engagement Activities:</div>
                          <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                            <li>• Week 14: CEO strategic briefing (via Board intro)</li>
                            <li>• Week 18: Reference visit to DEWA</li>
                            <li>• Week 22: PoC proposal presentation</li>
                          </ul>
                        </div>
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white mb-2">Deliverables:</div>
                          <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                            <li>• Detailed business case (validated ROI)</li>
                            <li>• Proof of concept scope (5 pilot sites)</li>
                            <li>• Implementation roadmap</li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Q2 2026 */}
                  <div className="relative">
                    <div className="absolute -left-9 top-2 w-4 h-4 bg-blue-500 rounded-full border-4 border-white dark:border-gray-900"></div>
                    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-xl p-6">
                      <h4 className="text-xl font-bold text-blue-900 dark:text-blue-200 mb-3">Q2 2026: PoC Approval & Contract</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white mb-2">Key Milestones:</div>
                          <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                            <li>• Month 7: PoC approval & funding (SAR 2M)</li>
                            <li>• Month 8: SBM partnership formalized</li>
                            <li>• Month 9: Contract negotiation & signing</li>
                          </ul>
                        </div>
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white mb-2">Success Criteria:</div>
                          <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                            <li>• Executive steering committee established</li>
                            <li>• Pilot sites selected (5 substations)</li>
                            <li>• Phase 1 roadmap agreed</li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Q3-Q4 2026 */}
                  <div className="relative">
                    <div className="absolute -left-9 top-2 w-4 h-4 bg-yellow-500 rounded-full border-4 border-white dark:border-gray-900"></div>
                    <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-xl p-6">
                      <h4 className="text-xl font-bold text-yellow-900 dark:text-yellow-200 mb-3">Q3-Q4 2026: Pilot Execution</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white mb-2">Implementation:</div>
                          <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                            <li>• Month 10-12: PoC deployment (5 critical assets)</li>
                            <li>• Month 13: Results validation</li>
                            <li>• Month 14: Business case update</li>
                          </ul>
                        </div>
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white mb-2">Next Phase:</div>
                          <ul className="text-gray-700 dark:text-gray-300 space-y-1">
                            <li>• Phase 1 expansion proposal (SAR 12M)</li>
                            <li>• 200 user rollout planning</li>
                            <li>• Contract negotiation for full deployment</li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )
        },

        // Slide 25: Success Metrics & Governance - CREATE NEW
        {
          title: "Success Metrics & Governance",
          subtitle: "Ongoing Account Management Framework",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-purple-800 dark:text-purple-300">📊 Account Metrics</h3>
                  <div className="space-y-3 text-sm">
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-700 dark:text-gray-300">3-Year TCV Target:</span>
                        <span className="font-bold text-purple-700 dark:text-purple-400">SAR 45M</span>
                      </div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-700 dark:text-gray-300">Year 1 Milestone (Pilot):</span>
                        <span className="font-bold text-gray-900 dark:text-white">SAR 2M</span>
                      </div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-700 dark:text-gray-300">Executive Meetings (Q1-Q2):</span>
                        <span className="font-bold text-gray-900 dark:text-white">8+ C-suite</span>
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between items-center">
                        <span className="text-gray-700 dark:text-gray-300">Champion Development:</span>
                        <span className="font-bold text-gray-900 dark:text-white">EVP Operations</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
                  <h3 className="text-xl font-bold mb-4 text-green-800 dark:text-green-300">✓ Milestone Tracking</h3>
                  <div className="space-y-3 text-sm">
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-700 dark:text-gray-300">CEO Intro:</span>
                        <span className="font-semibold text-blue-600 dark:text-blue-400">Q1 2026</span>
                      </div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-700 dark:text-gray-300">Pilot Approval:</span>
                        <span className="font-semibold text-blue-600 dark:text-blue-400">Q2 2026</span>
                      </div>
                    </div>
                    <div className="pb-2 border-b border-gray-200 dark:border-gray-700">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-700 dark:text-gray-300">PoC Deployment:</span>
                        <span className="font-semibold text-blue-600 dark:text-blue-400">Q3-Q4 2026</span>
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between items-center">
                        <span className="text-gray-700 dark:text-gray-300">Phase 1 Contract:</span>
                        <span className="font-semibold text-blue-600 dark:text-blue-400">Q1 2027</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/30 dark:to-blue-900/30 rounded-xl p-6 border border-purple-200 dark:border-purple-700">
                <h3 className="text-2xl font-bold mb-4 text-purple-900 dark:text-purple-200">Governance Model</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
                  <div>
                    <div className="font-bold text-purple-800 dark:text-purple-300 mb-2">Monthly</div>
                    <div className="text-gray-700 dark:text-gray-300 mb-2">Internal Account Team Review</div>
                    <ul className="text-gray-600 dark:text-gray-400 space-y-1 text-xs">
                      <li>• Pipeline & forecast update</li>
                      <li>• Risk assessment & mitigation</li>
                      <li>• Next actions & resource allocation</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-bold text-green-800 dark:text-green-300 mb-2">Quarterly</div>
                    <div className="text-gray-700 dark:text-gray-300 mb-2">Executive Sponsor Engagement</div>
                    <ul className="text-gray-600 dark:text-gray-400 space-y-1 text-xs">
                      <li>• IFS VP + SEC EVP Operations</li>
                      <li>• Strategic progress review</li>
                      <li>• Executive relationship building</li>
                    </ul>
                  </div>
                  <div>
                    <div className="font-bold text-blue-800 dark:text-blue-300 mb-2">Bi-Annually</div>
                    <div className="text-gray-700 dark:text-gray-300 mb-2">Strategic Business Review</div>
                    <ul className="text-gray-600 dark:text-gray-400 space-y-1 text-xs">
                      <li>• Account plan vs. actuals</li>
                      <li>• Adjust strategy & tactics</li>
                      <li>• Long-term roadmap alignment</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 p-4 rounded-r-xl">
                <div className="flex items-start">
                  <Target className="mr-3 mt-1 text-red-600" size={24} />
                  <div>
                    <div className="font-bold text-red-900 dark:text-red-200 mb-2">Priority: P0 - Strategic Account</div>
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      SEC requires dedicated executive sponsorship (IFS VP), full-time account team, and quarterly executive touchpoints.
                      Success at SEC opens door to additional Saudi utilities (SWPC, ECRA) representing SAR 100M+ expansion potential.
                    </div>
                  </div>
                </div>
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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-700/50 dark:bg-gray-900 transition-colors flex">
      {/* Mobile Overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 md:hidden z-40"
          onClick={() => setIsSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Navigation */}
      <div className={`fixed left-0 top-0 h-full bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 shadow-lg transition-all duration-300 z-50 overflow-y-auto ${
        isSidebarOpen ? 'w-80' : 'w-0'
      }`}>
        <div className={`${isSidebarOpen ? 'p-6' : 'hidden'}`}>
          {/* Sidebar Header */}
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white dark:text-white">Navigation</h2>
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:bg-gray-700 dark:hover:bg-gray-700 transition-colors"
              aria-label="Close sidebar"
            >
              <X size={20} className="text-gray-600 dark:text-gray-300 dark:text-gray-400" />
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
                        : 'hover:bg-gray-50 dark:bg-gray-700/50 dark:hover:bg-gray-700/50 border-l-4 border-transparent'
                    }`}
                    style={isCurrentSection ? { borderLeftColor: section.color } : {}}
                  >
                    <div className="flex items-center space-x-3 flex-1 text-left">
                      <Icon
                        size={18}
                        className={isCurrentSection ? 'text-purple-700 dark:text-purple-400 dark:text-purple-400' : 'text-gray-600 dark:text-gray-300 dark:text-gray-400'}
                        style={isCurrentSection ? { color: section.color } : {}}
                      />
                      <div className="flex-1">
                        <div className={`text-sm font-semibold ${
                          isCurrentSection
                            ? 'text-purple-700 dark:text-purple-400 dark:text-purple-400'
                            : 'text-gray-900 dark:text-white dark:text-white'
                        }`}>
                          {section.title}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 dark:text-gray-400 mt-0.5">
                          {section.slides.length} slides
                        </div>
                      </div>
                    </div>
                    {isExpanded ? (
                      <ChevronUp size={16} className="text-gray-500 dark:text-gray-400 dark:text-gray-400" />
                    ) : (
                      <ChevronDown size={16} className="text-gray-500 dark:text-gray-400 dark:text-gray-400" />
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
                                ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 dark:text-purple-400 font-medium'
                                : 'hover:bg-gray-50 dark:bg-gray-700/50 dark:hover:bg-gray-700/50 text-gray-700 dark:text-gray-200 dark:text-gray-300'
                            }`}
                          >
                            <div className={`w-1.5 h-1.5 rounded-full ${
                              isCurrentSlide ? 'bg-purple-700 dark:bg-purple-400' : 'bg-gray-300 dark:bg-gray-600'
                            }`}
                            style={isCurrentSlide ? { backgroundColor: section.color } : {}}
                            />
                            <span className="text-sm flex-1">{slide.title}</span>
                            <span className="text-xs text-gray-400 dark:text-gray-500 dark:text-gray-400">{slideIdx + 1}</span>
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
      <div className={`flex-1 transition-all duration-300 ${isSidebarOpen ? 'md:ml-80' : 'ml-0'}`}>
        {/* Header */}
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm sticky top-0 z-40">
          <div className="max-w-7xl mx-auto px-8 py-4">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-3">
              <div className="flex items-center space-x-3 md:space-x-6 flex-wrap">
                {/* Sidebar Toggle */}
                {!isSidebarOpen && (
                  <button
                    onClick={() => setIsSidebarOpen(true)}
                    className="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 transition-colors"
                    aria-label="Open sidebar"
                  >
                    <Menu size={20} className="text-gray-700 dark:text-gray-200 dark:text-gray-300" />
                  </button>
                )}
                <IFSLogo />
                <div className="h-10 w-px bg-gray-300 dark:bg-gray-600 hidden sm:block"></div>
                <SECLogo />
                <div className="h-10 w-px bg-gray-300 dark:bg-gray-600 hidden md:block"></div>
                <div className="hidden md:block">
                  <div className="text-lg font-bold text-gray-900 dark:text-white dark:text-white">Strategic Account Plan</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 dark:text-gray-400 font-medium mt-0.5">Saudi Electricity Company</div>
                </div>
              </div>
              <div className="flex items-center space-x-3 md:space-x-6">
                <div className="text-right hidden sm:block">
                  <div className="text-sm font-semibold text-purple-700 dark:text-purple-400 dark:text-purple-400">
                    Section {currentSection + 1} of {sections.length}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 dark:text-gray-400 mt-0.5">
                    {currentSectionData.title}
                  </div>
                </div>
                {/* Theme Toggle */}
                <button
                  onClick={() => setIsDarkMode(!isDarkMode)}
                  className="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 transition-colors"
                  aria-label="Toggle theme"
                >
                  {isDarkMode ? (
                    <Sun size={20} className="text-yellow-500" />
                  ) : (
                    <Moon size={20} className="text-gray-700 dark:text-gray-200" />
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
                                  idx < currentSection ? (isDarkMode ? '#4b5563' : '#d1d5db') : (isDarkMode ? '#374151' : '#e5e7eb')
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
              <span className="text-xs font-medium text-gray-600 dark:text-gray-300 dark:text-gray-400">Slide:</span>
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
            <div className="text-xs text-gray-500 dark:text-gray-400 dark:text-gray-400 font-medium">
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
                  className: "text-purple-700 dark:text-purple-400 dark:text-purple-400",
                  style: { color: currentSectionData.color }
                })}
                <h1 className="text-4xl font-bold text-gray-900 dark:text-white dark:text-white">{currentSlideData.title}</h1>
              </div>
              {currentSlideData.subtitle && (
                <p className="text-xl text-gray-600 dark:text-gray-300 dark:text-gray-300 ml-14">{currentSlideData.subtitle}</p>
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
                className="flex items-center space-x-2 px-6 py-3 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-all font-medium disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-gray-100 dark:disabled:hover:bg-gray-700 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                aria-label="Previous slide"
              >
                <ChevronLeft size={20} />
                <span>Previous</span>
              </button>

              <div className="flex items-center space-x-3">
                {currentSectionData.slides.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={() => setCurrentSlide(idx)}
                    className={`h-2.5 rounded-full transition-all focus:ring-2 focus:ring-purple-500 focus:outline-none ${
                      currentSlide === idx ? 'w-10 bg-purple-700' : 'w-2.5 bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500'
                    }`}
                    style={currentSlide === idx ? { backgroundColor: currentSectionData.color } : {}}
                    aria-label={`Go to slide ${idx + 1}`}
                    aria-current={currentSlide === idx ? 'true' : 'false'}
                  />
                ))}
              </div>

              <button
                onClick={nextSlide}
                disabled={currentSection === sections.length - 1 && currentSlide === currentSectionData.slides.length - 1}
                className="flex items-center space-x-2 px-6 py-3 bg-purple-700 text-white rounded-lg hover:bg-purple-800 transition-all font-medium disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-purple-700 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                style={{ backgroundColor: currentSectionData.color }}
                aria-label="Next slide"
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
          <div className="text-center text-gray-500 dark:text-gray-400 dark:text-gray-400 text-sm">
            <p className="font-medium">© 2024 IFS - Confidential &amp; Proprietary</p>
            <p className="mt-2">Saudi Electricity Company Strategic Account Plan</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SECAccountPlanning;
