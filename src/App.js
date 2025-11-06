import React, { useState } from 'react';
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
  Shield
} from 'lucide-react';

const SECAccountPlanning = () => {
  const [currentSection, setCurrentSection] = useState(0);
  const [currentSlide, setCurrentSlide] = useState(0);

  const sections = [
    {
      title: "Executive Summary",
      icon: Target,
      color: "from-blue-600 to-purple-600",
      slides: [
        {
          title: "Saudi Electricity Company",
          subtitle: "Strategic Account Plan - IFS.ai Digital Transformation",
          content: (
            <div className="space-y-6">
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white/10 backdrop-blur p-6 rounded-lg text-center">
                  <Users className="mx-auto mb-2" size={32} />
                  <div className="text-3xl font-bold">11.2M</div>
                  <div className="text-sm">Customers Served</div>
                </div>
                <div className="bg-white/10 backdrop-blur p-6 rounded-lg text-center">
                  <Zap className="mx-auto mb-2" size={32} />
                  <div className="text-3xl font-bold">70.7 GW</div>
                  <div className="text-sm">Peak Load 2023</div>
                </div>
                <div className="bg-white/10 backdrop-blur p-6 rounded-lg text-center">
                  <DollarSign className="mx-auto mb-2" size={32} />
                  <div className="text-3xl font-bold">$133B</div>
                  <div className="text-sm">Total Assets</div>
                </div>
              </div>
              <div className="bg-white/5 backdrop-blur rounded-lg p-6">
                <h3 className="text-xl font-semibold mb-3">Vision 2030 Alignment</h3>
                <p className="text-white/90">
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
            <div className="space-y-4">
              <div className="bg-white/10 backdrop-blur rounded-lg p-6">
                <h3 className="text-xl font-semibold mb-3 flex items-center">
                  <Globe className="mr-2" /> Market Size & Growth
                </h3>
                <ul className="space-y-2 text-white/90">
                  <li className="flex items-start">
                    <ChevronRight className="mr-2 mt-1 flex-shrink-0" size={16} />
                    <span>$81.7B market value (2024) with steady growth trajectory</span>
                  </li>
                  <li className="flex items-start">
                    <ChevronRight className="mr-2 mt-1 flex-shrink-0" size={16} />
                    <span>5% annual demand growth driven by Vision 2030 initiatives</span>
                  </li>
                  <li className="flex items-start">
                    <ChevronRight className="mr-2 mt-1 flex-shrink-0" size={16} />
                    <span>Record peak load of 70,663 MW in 2023 (8.2% YoY increase)</span>
                  </li>
                  <li className="flex items-start">
                    <ChevronRight className="mr-2 mt-1 flex-shrink-0" size={16} />
                    <span>MENA electricity demand projected to rise 50% by 2035</span>
                  </li>
                </ul>
              </div>
              <div className="bg-white/10 backdrop-blur rounded-lg p-6">
                <h3 className="text-xl font-semibold mb-3">Regulatory Framework</h3>
                <p className="text-white/90">
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
      color: "from-purple-600 to-pink-600",
      slides: [
        {
          title: "Industry Mega-Trends",
          subtitle: "Transforming the Utility Landscape",
          content: (
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-green-300">🌱 Decarbonization & Energy Transition</h4>
                <p className="text-sm text-white/80">
                  50% renewables by 2030, net-zero by 2050. $1.74T invested in clean energy globally in 2023.
                </p>
              </div>
              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-blue-300">⚡ Digital Grid & Smart Networks</h4>
                <p className="text-sm text-white/80">
                  23x growth in connected energy devices (2011-2021). AI-driven predictive maintenance and grid automation.
                </p>
              </div>
              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-yellow-300">🔋 Distributed Energy Resources</h4>
                <p className="text-sm text-white/80">
                  Rise of prosumers, rooftop solar, battery storage requiring two-way energy flow management.
                </p>
              </div>
              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-purple-300">🚗 Electrification of Transport</h4>
                <p className="text-sm text-white/80">
                  EVs reached 15% of global sales in 2023. Saudi targets 30% EV penetration in Riyadh by 2030.
                </p>
              </div>
              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-orange-300">🎯 Customer-Centric Innovation</h4>
                <p className="text-sm text-white/80">
                  Seamless digital engagement, personalized services. SEC achieved 81% customer satisfaction in 2023.
                </p>
              </div>
              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-red-300">🛡️ Grid Resilience & Cybersecurity</h4>
                <p className="text-sm text-white/80">
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
            <div className="space-y-3">
              <div className="bg-gradient-to-r from-red-600/20 to-green-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-red-300">FROM: Carbon-intensive generation</span>
                  <ChevronRight size={20} />
                  <span className="text-sm font-semibold text-green-300">TO: 50% renewable & 50% gas by 2030</span>
                </div>
                <p className="text-xs text-white/80">KPI: Renewables 0% → 50%, Liquid fuel eliminated by 2030, Net-zero by 2050</p>
              </div>

              <div className="bg-gradient-to-r from-red-600/20 to-green-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-red-300">FROM: Reactive maintenance</span>
                  <ChevronRight size={20} />
                  <span className="text-sm font-semibold text-green-300">TO: Predictive, condition-based</span>
                </div>
                <p className="text-xs text-white/80">KPI: 30-50% reduction in unplanned outages, >90% equipment effectiveness</p>
              </div>

              <div className="bg-gradient-to-r from-red-600/20 to-green-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-red-300">FROM: Siloed, manual processes</span>
                  <ChevronRight size={20} />
                  <span className="text-sm font-semibold text-green-300">TO: Integrated digital operations</span>
                </div>
                <p className="text-xs text-white/80">KPI: 30-40% faster process cycles, single source of truth, digital maturity 4.5/5</p>
              </div>

              <div className="bg-gradient-to-r from-red-600/20 to-green-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-red-300">FROM: Commodity supplier mindset</span>
                  <ChevronRight size={20} />
                  <span className="text-sm font-semibold text-green-300">TO: Customer-centric services</span>
                </div>
                <p className="text-xs text-white/80">KPI: Customer satisfaction 81% → >90%, First-contact resolution >85%</p>
              </div>

              <div className="bg-gradient-to-r from-red-600/20 to-green-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-red-300">FROM: State-dependent financials</span>
                  <ChevronRight size={20} />
                  <span className="text-sm font-semibold text-green-300">TO: Commercially sustainable</span>
                </div>
                <p className="text-xs text-white/80">KPI: EBITDA margin ~30%, Gov subsidy <2%, Investment-grade credit maintained</p>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "Stakeholder Landscape",
      icon: Users,
      color: "from-pink-600 to-red-600",
      slides: [
        {
          title: "Executive Leadership",
          subtitle: "Key Decision Makers",
          content: (
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-blue-300">CEO - Eng. Khaled Al-Gnoon</h4>
                <p className="text-sm text-white/80 mb-2"><strong>Focus:</strong> Vision 2030 delivery, financial sustainability, reliability</p>
                <p className="text-sm text-white/70"><strong>Pain Points:</strong> Balancing SAR 500B capex with debt management, avoiding major outages, driving transformation</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-green-300">CFO / SVP Finance</h4>
                <p className="text-sm text-white/80 mb-2"><strong>Focus:</strong> Capital efficiency, cost control, credit rating maintenance</p>
                <p className="text-sm text-white/70"><strong>Pain Points:</strong> Managing SAR 45B annual capex, optimizing O&M, RAB model compliance</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-purple-300">COO / EVP Operations</h4>
                <p className="text-sm text-white/80 mb-2"><strong>Focus:</strong> Reliability, operational efficiency, safety excellence</p>
                <p className="text-sm text-white/70"><strong>Pain Points:</strong> Coordination across divisions, minimizing SAIDI/SAIFI, workforce optimization</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h4 className="font-semibold mb-2 text-yellow-300">CIO / Chief Digital Officer</h4>
                <p className="text-sm text-white/80 mb-2"><strong>Focus:</strong> Digital transformation, system modernization, cybersecurity</p>
                <p className="text-sm text-white/70"><strong>Pain Points:</strong> Heterogeneous systems, data silos, managing SAP/Oracle upgrades</p>
              </div>
            </div>
          )
        },
        {
          title: "Operational Leaders",
          subtitle: "Business Unit Executives",
          content: (
            <div className="space-y-3">
              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 flex items-center">
                  <Zap className="mr-2 text-yellow-300" size={20} />
                  EVP Generation
                </h4>
                <p className="text-sm text-white/80"><strong>Challenge:</strong> Maximize plant reliability, minimize forced outages, optimize fuel efficiency</p>
                <p className="text-xs text-white/60 mt-1">IFS Value: Predictive maintenance to prevent unplanned downtime, integrated project management for overhauls</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 flex items-center">
                  <Zap className="mr-2 text-blue-300" size={20} />
                  EVP Transmission (National Grid SA)
                </h4>
                <p className="text-sm text-white/80"><strong>Challenge:</strong> Resilient grid expansion, managing 84,000 km of lines, renewable integration</p>
                <p className="text-xs text-white/60 mt-1">IFS Value: Linear asset management, GIS integration, predictive analytics for grid assets</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 flex items-center">
                  <Users className="mr-2 text-green-300" size={20} />
                  EVP Distribution & Customer Services
                </h4>
                <p className="text-sm text-white/80"><strong>Challenge:</strong> Faster outage restoration, customer satisfaction >90%, efficient new connections</p>
                <p className="text-xs text-white/60 mt-1">IFS Value: FSM optimization, mobile workforce, proactive customer communications</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 flex items-center">
                  <Target className="mr-2 text-purple-300" size={20} />
                  VP Asset Management
                </h4>
                <p className="text-sm text-white/80"><strong>Challenge:</strong> Shift from reactive to predictive maintenance, spare parts optimization</p>
                <p className="text-xs text-white/60 mt-1">IFS Value: Comprehensive EAM, IoT/AI integration, condition-based maintenance strategies</p>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "IFS Solution Portfolio",
      icon: Briefcase,
      color: "from-cyan-600 to-blue-600",
      slides: [
        {
          title: "Comprehensive Use Cases",
          subtitle: "Addressing SEC's Critical Needs",
          content: (
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-gradient-to-br from-blue-600/20 to-purple-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-2">🔮 Predictive Maintenance for Power Plants</h4>
                <p className="text-xs text-white/80 mb-2">IoT sensors + ML to predict equipment failures before unplanned outages</p>
                <div className="text-xs text-green-300 font-semibold">ROI: 12-24 months | 20-30% reduction in forced outages</div>
              </div>

              <div className="bg-gradient-to-br from-purple-600/20 to-pink-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-2">⚡ Outage Management & Fast Restoration</h4>
                <p className="text-xs text-white/80 mb-2">Streamlined end-to-end outage process with optimized crew dispatch</p>
                <div className="text-xs text-green-300 font-semibold">ROI: 6-12 months | 15% reduction in SAIDI</div>
              </div>

              <div className="bg-gradient-to-br from-pink-600/20 to-red-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-2">💰 Asset Investment Planning</h4>
                <p className="text-xs text-white/80 mb-2">Value-driven portfolio optimization for SAR 500B capex program</p>
                <div className="text-xs text-green-300 font-semibold">ROI: 12-18 months | 5% capital efficiency improvement</div>
              </div>

              <div className="bg-gradient-to-br from-red-600/20 to-orange-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-2">📱 Mobile Workforce Empowerment</h4>
                <p className="text-xs text-white/80 mb-2">Advanced mobile tools + AR support for first-time fix improvement</p>
                <div className="text-xs text-green-300 font-semibold">ROI: 6-12 months | 10% increase in FTF rate</div>
              </div>

              <div className="bg-gradient-to-br from-orange-600/20 to-yellow-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-2">📦 Inventory Optimization</h4>
                <p className="text-xs text-white/80 mb-2">Analytics-driven spare parts planning for billions in inventory</p>
                <div className="text-xs text-green-300 font-semibold">ROI: 12 months | 15% inventory reduction = SAR 750M freed</div>
              </div>

              <div className="bg-gradient-to-br from-yellow-600/20 to-green-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-2">🗺️ Linear Asset Management & GIS</h4>
                <p className="text-xs text-white/80 mb-2">Spatial integration for 84,000 km transmission network</p>
                <div className="text-xs text-green-300 font-semibold">ROI: 6-12 months | Faster fault location, reduced errors</div>
              </div>

              <div className="bg-gradient-to-br from-green-600/20 to-teal-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-2">🎯 Enterprise Project Management</h4>
                <p className="text-xs text-white/80 mb-2">Robust PM practices for on-time, on-budget capital projects</p>
                <div className="text-xs text-green-300 font-semibold">ROI: 12-24 months | Reduce overruns 10% → 5%</div>
              </div>

              <div className="bg-gradient-to-br from-teal-600/20 to-cyan-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-2">😊 Customer Experience Enhancement</h4>
                <p className="text-xs text-white/80 mb-2">Omnichannel communication, proactive outage alerts</p>
                <div className="text-xs text-green-300 font-semibold">ROI: 6-12 months | CSAT 81% → >90%, 20% call reduction</div>
              </div>
            </div>
          )
        },
        {
          title: "IFS Competitive Advantages",
          subtitle: "Why IFS Outperforms SAP, Oracle & Others",
          content: (
            <div className="space-y-3">
              <div className="bg-white/10 backdrop-blur rounded-lg p-4 border-l-4 border-blue-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <CheckCircle className="mr-2 text-blue-400" size={20} />
                  True End-to-End Integration
                </h4>
                <p className="text-sm text-white/80">One platform covering asset, workforce, supply chain, projects, service. SAP/Oracle require multiple products + heavy integration.</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4 border-l-4 border-green-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <CheckCircle className="mr-2 text-green-400" size={20} />
                  Best-in-Class Scheduling (PSO)
                </h4>
                <p className="text-sm text-white/80">AI-powered optimization consistently delivers 10-20% productivity improvements vs. competitors' basic scheduling.</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4 border-l-4 border-purple-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <CheckCircle className="mr-2 text-purple-400" size={20} />
                  Deep Utility Domain Expertise
                </h4>
                <p className="text-sm text-white/80">Built for utilities with linear asset management, GIS integration, crew shift planning out-of-the-box. No heavy customization needed.</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4 border-l-4 border-yellow-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <CheckCircle className="mr-2 text-yellow-400" size={20} />
                  Proven ROI: 414% Over 3 Years
                </h4>
                <p className="text-sm text-white/80">IDC study: $5.5M annual savings, 11-month payback. Includes 50% faster outage resolution, 30% lower IT complexity.</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4 border-l-4 border-red-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <CheckCircle className="mr-2 text-red-400" size={20} />
                  Modern UI & Mobility
                </h4>
                <p className="text-sm text-white/80">Intuitive, web-based interface with fully offline-capable mobile apps. SAP/Oracle UIs are clunky and complex by comparison.</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4 border-l-4 border-pink-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <CheckCircle className="mr-2 text-pink-400" size={20} />
                  Local Partnership + Global Expertise
                </h4>
                <p className="text-sm text-white/80">Strategic partnership with Saudi Business Machines (SBM) ensures strong local presence + IFS's global R&D backing.</p>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "Business Case",
      icon: DollarSign,
      color: "from-green-600 to-teal-600",
      slides: [
        {
          title: "Financial Impact",
          subtitle: "Quantified Benefits & ROI",
          content: (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gradient-to-br from-green-600/30 to-teal-600/30 backdrop-blur rounded-lg p-5 text-center border border-white/20">
                  <div className="text-4xl font-bold text-green-300 mb-2">SAR 2B</div>
                  <div className="text-sm text-white/80">Annual O&M Savings</div>
                  <div className="text-xs text-white/60 mt-2">10-15% reduction through optimized maintenance & scheduling</div>
                </div>

                <div className="bg-gradient-to-br from-blue-600/30 to-purple-600/30 backdrop-blur rounded-lg p-5 text-center border border-white/20">
                  <div className="text-4xl font-bold text-blue-300 mb-2">SAR 2B</div>
                  <div className="text-sm text-white/80">Annual Capex Optimization</div>
                  <div className="text-xs text-white/60 mt-2">5% efficiency improvement on SAR 40B annual capex</div>
                </div>

                <div className="bg-gradient-to-br from-purple-600/30 to-pink-600/30 backdrop-blur rounded-lg p-5 text-center border border-white/20">
                  <div className="text-4xl font-bold text-purple-300 mb-2">SAR 750M</div>
                  <div className="text-sm text-white/80">Working Capital Release</div>
                  <div className="text-xs text-white/60 mt-2">15% inventory reduction one-time cash benefit</div>
                </div>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h3 className="text-xl font-semibold mb-3">5-Year ROI Summary</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-white/60 mb-1">Total Investment</div>
                    <div className="text-2xl font-bold text-red-300">SAR 300-400M</div>
                    <div className="text-xs text-white/50">Software, implementation, training</div>
                  </div>
                  <div>
                    <div className="text-white/60 mb-1">Total Benefits (5 years)</div>
                    <div className="text-2xl font-bold text-green-300">SAR 10B+</div>
                    <div className="text-xs text-white/50">O&M + Capex + Inventory + Productivity</div>
                  </div>
                  <div>
                    <div className="text-white/60 mb-1">Payback Period</div>
                    <div className="text-2xl font-bold text-yellow-300">&lt;2 Years</div>
                    <div className="text-xs text-white/50">Early benefits self-fund later phases</div>
                  </div>
                  <div>
                    <div className="text-white/60 mb-1">5-Year ROI</div>
                    <div className="text-2xl font-bold text-blue-300">4:1+</div>
                    <div className="text-xs text-white/50">Consistent with IDC 414% ROI finding</div>
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
            <div className="space-y-3">
              <div className="bg-gradient-to-r from-blue-600/20 to-cyan-600/20 backdrop-blur rounded-lg p-4 border-l-4 border-blue-400">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold">Phase 1: Foundation & Quick Wins</h4>
                  <span className="text-sm text-blue-300">Months 0-6</span>
                </div>
                <p className="text-sm text-white/80 mb-2">
                  Core platform setup, inventory optimization, basic work order management pilot
                </p>
                <div className="text-xs text-green-300">Deliverable: Pilot showing inventory reduction + improved maintenance backlog</div>
              </div>

              <div className="bg-gradient-to-r from-cyan-600/20 to-teal-600/20 backdrop-blur rounded-lg p-4 border-l-4 border-cyan-400">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold">Phase 2: Core EAM & FSM Rollout</h4>
                  <span className="text-sm text-cyan-300">Months 7-12</span>
                </div>
                <p className="text-sm text-white/80 mb-2">
                  Full maintenance mgmt across Gen/T/D, mobile FSM + PSO scheduling, Asset Investment Planning
                </p>
                <div className="text-xs text-green-300">Deliverable: 15% reduction in emergency maintenance, AIP influencing budget cycle</div>
              </div>

              <div className="bg-gradient-to-r from-teal-600/20 to-green-600/20 backdrop-blur rounded-lg p-4 border-l-4 border-teal-400">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold">Phase 3: Advanced Capabilities</h4>
                  <span className="text-sm text-teal-300">Months 13-18</span>
                </div>
                <p className="text-sm text-white/80 mb-2">
                  APM analytics with IoT, HSE & Quality modules, proactive customer communications
                </p>
                <div className="text-xs text-green-300">Deliverable: Predictive maintenance demonstrating reduced downtime, CSAT improvements</div>
              </div>

              <div className="bg-gradient-to-r from-green-600/20 to-yellow-600/20 backdrop-blur rounded-lg p-4 border-l-4 border-green-400">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold">Phase 4: Stabilization & Optimization</h4>
                  <span className="text-sm text-green-300">Months 19-24</span>
                </div>
                <p className="text-sm text-white/80 mb-2">
                  KPI monitoring, system fine-tuning, Center of Excellence establishment, legacy system retirement
                </p>
                <div className="text-xs text-green-300">Deliverable: Full stabilization, documented ROI achievement, handoff to SEC team</div>
              </div>
            </div>
          )
        }
      ]
    },
    {
      title: "Proof Points & SWOT",
      icon: Award,
      color: "from-yellow-600 to-orange-600",
      slides: [
        {
          title: "Proven Success Stories",
          subtitle: "Real Results from Similar Utilities",
          content: (
            <div className="space-y-3">
              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 text-blue-300">🏭 European T&D Utility</h4>
                <p className="text-sm text-white/80 mb-1"><strong>Challenge:</strong> High unplanned outage rates, reactive maintenance</p>
                <p className="text-sm text-green-300"><strong>Result:</strong> 25% reduction in unplanned outages over 3 years using IFS predictive maintenance</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 text-green-300">⚡ Colorado Springs Utilities (USA)</h4>
                <p className="text-sm text-white/80 mb-1"><strong>Challenge:</strong> Multi-utility coordination, emergency response efficiency</p>
                <p className="text-sm text-green-300"><strong>Result:</strong> Improved workforce safety & response with IFS, streamlined forest fire outage management</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 text-purple-300">📊 IDC Independent Study</h4>
                <p className="text-sm text-white/80 mb-1"><strong>Methodology:</strong> Analysis of IFS Cloud customers across industries</p>
                <p className="text-sm text-green-300"><strong>Result:</strong> Average 414% ROI over 3 years, $5.5M annual gains, 11-month payback, 50% faster issue resolution</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 text-yellow-300">🔧 Australian Utility</h4>
                <p className="text-sm text-white/80 mb-1"><strong>Challenge:</strong> Excess inventory tying up capital</p>
                <p className="text-sm text-green-300"><strong>Result:</strong> ~15% inventory value reduction using IFS integrated inventory planning</p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4">
                <h4 className="font-semibold mb-2 text-red-300">🌍 Global Energy Company</h4>
                <p className="text-sm text-white/80 mb-1"><strong>Challenge:</strong> Safety incident rates, HSE compliance</p>
                <p className="text-sm text-green-300"><strong>Result:</strong> 40% increase in near-miss reporting, 20% reduction in actual safety incidents using IFS HSE</p>
              </div>
            </div>
          )
        },
        {
          title: "SWOT Analysis",
          subtitle: "SEC's Strategic Position",
          content: (
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gradient-to-br from-green-600/20 to-teal-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-3 text-green-300">Strengths 💪</h4>
                <ul className="text-xs space-y-1 text-white/80">
                  <li>• Dominant market position (100% T&D, 66% generation)</li>
                  <li>• Strong government backing (81% ownership)</li>
                  <li>• Vision 2030 alignment & political will</li>
                  <li>• Recent track record: 10M smart meters, 81% CSAT</li>
                  <li>• 94% Saudi workforce, skilled & experienced</li>
                  <li>• Robust $133B asset base</li>
                </ul>
              </div>

              <div className="bg-gradient-to-br from-red-600/20 to-orange-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-3 text-red-300">Weaknesses 🔍</h4>
                <ul className="text-xs space-y-1 text-white/80">
                  <li>• Legacy systems & siloed processes</li>
                  <li>• High debt (~SAR 297B liabilities)</li>
                  <li>• Aging asset components, reactive maintenance</li>
                  <li>• Complex organizational structure, slow decisions</li>
                  <li>• Customer service perception gaps (81% vs >90% target)</li>
                  <li>• Regulatory dependency on ECRA tariff decisions</li>
                </ul>
              </div>

              <div className="bg-gradient-to-br from-blue-600/20 to-purple-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-3 text-blue-300">Opportunities 🚀</h4>
                <ul className="text-xs space-y-1 text-white/80">
                  <li>• Vision 2030 investments & smart grid initiatives</li>
                  <li>• 130 GW renewable integration by 2030</li>
                  <li>• Sector reform opening new market roles</li>
                  <li>• AI/IoT digitalization for efficiency & service</li>
                  <li>• Mining 400+ TWh AMI data for new products</li>
                  <li>• Efficiency gains before next RAB rate reset</li>
                </ul>
              </div>

              <div className="bg-gradient-to-br from-yellow-600/20 to-red-600/20 backdrop-blur rounded-lg p-4 border border-white/20">
                <h4 className="font-semibold mb-3 text-yellow-300">Threats ⚠️</h4>
                <ul className="text-xs space-y-1 text-white/80">
                  <li>• Emerging competition from IPPs, potential retail opening</li>
                  <li>• Regulatory pressure & potential rate cuts</li>
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
            <div className="space-y-3">
              <div className="bg-gradient-to-r from-green-600/20 to-teal-600/20 backdrop-blur rounded-lg p-4 border-l-4 border-green-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <Globe className="mr-2 text-green-300" size={20} />
                  Environmental
                </h4>
                <p className="text-sm text-white/80 mb-2">
                  <strong>SEC Goal:</strong> Net-zero by 2050, 50% renewables by 2030, eliminate liquid fuel
                </p>
                <p className="text-xs text-white/70">
                  <strong>IFS Contribution:</strong> Track emissions data, optimize asset performance to reduce waste,
                  enable renewable integration, support ISO 14001 compliance. Better asset planning accelerates
                  inefficient plant retirement.
                </p>
              </div>

              <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/20 backdrop-blur rounded-lg p-4 border-l-4 border-blue-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <Users className="mr-2 text-blue-300" size={20} />
                  Social
                </h4>
                <p className="text-sm text-white/80 mb-2">
                  <strong>SEC Goal:</strong> Customer satisfaction >90%, reliability excellence, safe workforce
                </p>
                <p className="text-xs text-white/70">
                  <strong>IFS Contribution:</strong> Improve reliability (fewer outages = better quality of life),
                  proactive customer communication, enhanced safety through HSE module (20% injury reduction target),
                  digital training tools for workforce development.
                </p>
              </div>

              <div className="bg-gradient-to-r from-purple-600/20 to-pink-600/20 backdrop-blur rounded-lg p-4 border-l-4 border-purple-400">
                <h4 className="font-semibold mb-2 flex items-center">
                  <Shield className="mr-2 text-purple-300" size={20} />
                  Governance
                </h4>
                <p className="text-sm text-white/80 mb-2">
                  <strong>SEC Goal:</strong> Transparency, risk management, regulatory compliance, localization
                </p>
                <p className="text-xs text-white/70">
                  <strong>IFS Contribution:</strong> Comprehensive audit trails, segregation of duties, real-time
                  reporting to board/regulators, integrated risk management. Automated compliance tracking ensures
                  no missed requirements. Supports 70%+ local procurement tracking.
                </p>
              </div>

              <div className="bg-white/10 backdrop-blur rounded-lg p-4 text-center">
                <p className="text-sm text-white/80">
                  <strong className="text-green-300">Result:</strong> IFS serves as SEC's platform to not just meet but exceed ESG targets,
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
      color: "from-orange-600 to-red-600",
      slides: [
        {
          title: "Engagement Strategy",
          subtitle: "Path to Partnership",
          content: (
            <div className="space-y-4">
              <div className="bg-white/10 backdrop-blur rounded-lg p-5">
                <h3 className="text-xl font-semibold mb-3">Immediate Actions</h3>
                <div className="space-y-3">
                  <div className="flex items-start">
                    <div className="bg-blue-500 text-white rounded-full w-8 h-8 flex items-center justify-center mr-3 flex-shrink-0 font-bold">1</div>
                    <div>
                      <h4 className="font-semibold text-white">Executive Briefing</h4>
                      <p className="text-sm text-white/80">Schedule presentation with CIO/CDO and operational EVPs showcasing IFS capabilities + SEC-specific value proposition</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="bg-green-500 text-white rounded-full w-8 h-8 flex items-center justify-center mr-3 flex-shrink-0 font-bold">2</div>
                    <div>
                      <h4 className="font-semibold text-white">Workshop Series</h4>
                      <p className="text-sm text-white/80">Conduct focused workshops with key departments: Generation maintenance, Distribution ops, Asset planning, Customer service</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="bg-purple-500 text-white rounded-full w-8 h-8 flex items-center justify-center mr-3 flex-shrink-0 font-bold">3</div>
                    <div>
                      <h4 className="font-semibold text-white">Reference Visits</h4>
                      <p className="text-sm text-white/80">Arrange site visits to similar utilities using IFS (Dubai, Europe, or regional) to see system in action</p>
                    </div>
                  </div>

                  <div className="flex items-start">
                    <div className="bg-yellow-500 text-white rounded-full w-8 h-8 flex items-center justify-center mr-3 flex-shrink-0 font-bold">4</div>
                    <div>
                      <h4 className="font-semibold text-white">Pilot Proposal</h4>
                      <p className="text-sm text-white/80">Develop detailed proposal for Phase 1 pilot (6 months) in selected region/facility to demonstrate quick wins</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-blue-600/30 to-purple-600/30 backdrop-blur rounded-lg p-5 border border-white/20">
                <h3 className="text-lg font-semibold mb-2">Key Contacts</h3>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-white/60">Account Executive</p>
                    <p className="font-semibold">Mark Marawy</p>
                  </div>
                  <div>
                    <p className="text-white/60">Local Partner</p>
                    <p className="font-semibold">Saudi Business Machines (SBM)</p>
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
            <div className="space-y-4">
              <div className="bg-gradient-to-br from-blue-600/30 to-purple-600/30 backdrop-blur rounded-lg p-6 border border-white/30">
                <h3 className="text-2xl font-bold mb-4 text-center">Empowering the Kingdom's Future, Today</h3>
                <p className="text-white/90 text-center mb-6">
                  SEC's mission is evolving from keeping the lights on to driving strategic national outcomes:
                  reliability, sustainability, and service excellence.
                </p>

                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="bg-white/10 rounded-lg p-4">
                    <h4 className="font-semibold mb-2 text-green-300">✓ Vision 2030 Alignment</h4>
                    <p className="text-xs text-white/80">Digital transformation imperative, sustainability mandates, customer service excellence</p>
                  </div>
                  <div className="bg-white/10 rounded-lg p-4">
                    <h4 className="font-semibold mb-2 text-blue-300">✓ Market Timing</h4>
                    <p className="text-xs text-white/80">RAB model stable, renewables ramping up, smart meter foundation in place</p>
                  </div>
                  <div className="bg-white/10 rounded-lg p-4">
                    <h4 className="font-semibold mb-2 text-purple-300">✓ Proven Technology</h4>
                    <p className="text-xs text-white/80">IFS battle-tested with major utilities, 414% ROI validated by IDC, 97%+ renewal rate</p>
                  </div>
                  <div className="bg-white/10 rounded-lg p-4">
                    <h4 className="font-semibold mb-2 text-yellow-300">✓ Local Partnership</h4>
                    <p className="text-xs text-white/80">SBM alliance ensures on-ground support, Arabic language, cultural alignment</p>
                  </div>
                </div>

                <div className="bg-gradient-to-r from-green-600/30 to-teal-600/30 rounded-lg p-5 text-center">
                  <p className="text-lg font-semibold mb-2">
                    "SEC has always kept the Kingdom running"
                  </p>
                  <p className="text-xl font-bold text-green-300">
                    Now, by digitally transforming with IFS, SEC will supercharge its operational
                    excellence and agility to not just meet the future, but create it.
                  </p>
                </div>
              </div>

              <div className="text-center">
                <p className="text-2xl font-bold text-white mb-2">Let's Begin This Journey Together</p>
                <p className="text-white/80">IFS stands ready as your committed partner in SEC's transformation</p>
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white">
      {/* Header */}
      <div className="bg-black/30 backdrop-blur-sm border-b border-white/10">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                IFS.ai
              </div>
              <div className="text-sm text-white/60">|</div>
              <div className="text-lg font-semibold">SEC Account Planning</div>
            </div>
            <div className="text-sm text-white/60">
              {currentSection + 1} of {sections.length} • Slide {currentSlide + 1} of {currentSectionData.slides.length}
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="bg-black/20 backdrop-blur border-b border-white/10">
        <div className="container mx-auto px-6">
          <div className="flex space-x-1 overflow-x-auto">
            {sections.map((section, idx) => {
              const Icon = section.icon;
              return (
                <button
                  key={idx}
                  onClick={() => goToSection(idx)}
                  className={`flex items-center space-x-2 px-6 py-3 transition-all whitespace-nowrap ${
                    currentSection === idx
                      ? `bg-gradient-to-r ${section.color} text-white font-semibold`
                      : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon size={18} />
                  <span>{section.title}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-12">
        <div className={`bg-gradient-to-br ${currentSectionData.color} rounded-2xl shadow-2xl overflow-hidden`}>
          <div className="p-12">
            {/* Slide Header */}
            <div className="mb-8">
              <div className="flex items-center space-x-3 mb-3">
                {React.createElement(currentSectionData.icon, { size: 32, className: "text-white/90" })}
                <h1 className="text-4xl font-bold">{currentSlideData.title}</h1>
              </div>
              {currentSlideData.subtitle && (
                <p className="text-xl text-white/80 ml-11">{currentSlideData.subtitle}</p>
              )}
            </div>

            {/* Slide Content */}
            <div className="min-h-[400px]">
              {currentSlideData.content}
            </div>

            {/* Slide Navigation */}
            <div className="flex items-center justify-between mt-12 pt-8 border-t border-white/20">
              <button
                onClick={prevSlide}
                disabled={currentSection === 0 && currentSlide === 0}
                className="flex items-center space-x-2 px-6 py-3 bg-white/10 backdrop-blur rounded-lg hover:bg-white/20 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft size={20} />
                <span>Previous</span>
              </button>

              <div className="flex items-center space-x-2">
                {currentSectionData.slides.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={() => setCurrentSlide(idx)}
                    className={`w-2 h-2 rounded-full transition-all ${
                      currentSlide === idx ? 'bg-white w-8' : 'bg-white/30 hover:bg-white/50'
                    }`}
                  />
                ))}
              </div>

              <button
                onClick={nextSlide}
                disabled={currentSection === sections.length - 1 && currentSlide === currentSectionData.slides.length - 1}
                className="flex items-center space-x-2 px-6 py-3 bg-white/10 backdrop-blur rounded-lg hover:bg-white/20 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <span>Next</span>
                <ChevronRight size={20} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="container mx-auto px-6 pb-8">
        <div className="text-center text-white/40 text-sm">
          <p>© 2024 IFS.ai - Confidential & Proprietary</p>
          <p className="mt-1">Saudi Electricity Company Strategic Account Plan</p>
        </div>
      </div>
    </div>
  );
};

export default SECAccountPlanning;
