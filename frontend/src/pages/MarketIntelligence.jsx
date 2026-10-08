import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Box, Container, Heading, Text, Flex, HStack, VStack, SimpleGrid,
  Select, Button, Badge, Table, Thead, Tbody, Tr, Th, Td, Input,
  Tabs, TabList, TabPanels, Tab, TabPanel, Card, CardBody, CardHeader,
  Stat, StatLabel, StatNumber, StatHelpText, StatArrow, Progress,
  IconButton, Tooltip, Link as ChakraLink, Spinner, Tag, Divider
} from '@chakra-ui/react'
import {
  TrendingUp, BarChart3, Layers, Calendar, ExternalLink,
  ChevronLeft, ChevronRight, Activity, ShieldCheck, Database,
  Search, SlidersHorizontal, RefreshCw, Smartphone
} from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend
} from 'recharts'
import {
  getMarketAnalytics, getMarketExplorer, getMarketListings,
  getMarketQuality, getMarketConditions
} from '../api'

const FORMAT_CURRENCY = (val) => {
  if (!val && val !== 0) return '—'
  return new Intl.NumberFormat('vi-VN').format(val) + ' đ'
}

export default function MarketIntelligence() {
  // Filters
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedBrand, setSelectedBrand] = useState('')
  const [selectedProduct, setSelectedProduct] = useState('1') // default to iPhone 16
  const [selectedVariant, setSelectedVariant] = useState('1') // default to 128GB
  const [selectedCondition, setSelectedCondition] = useState('1') // default to N0 (New Sealed)
  const [timeframeDays, setTimeframeDays] = useState(30)
  const [distributionSource, setDistributionSource] = useState('')
  const [rawPage, setRawPage] = useState(1)

  // 1. Fetch Taxonomy Hierarchy
  const { data: explorerData = [] } = useQuery({
    queryKey: ['marketExplorer'],
    queryFn: () => getMarketExplorer().then(r => r.data)
  })

  // 2. Fetch Conditions
  const { data: conditionsData = [] } = useQuery({
    queryKey: ['marketConditions'],
    queryFn: () => getMarketConditions().then(r => r.data)
  })

  // 3. Fetch Analytics Data
  const analyticsParams = useMemo(() => ({
    product_id: selectedProduct ? Number(selectedProduct) : undefined,
    variant_id: selectedVariant ? Number(selectedVariant) : undefined,
    condition_id: selectedCondition ? Number(selectedCondition) : undefined,
    source_id: distributionSource ? Number(distributionSource) : undefined,
    days: timeframeDays
  }), [selectedProduct, selectedVariant, selectedCondition, distributionSource, timeframeDays])

  const { data: analytics = null, isLoading: loadingAnalytics, refetch: refetchAnalytics } = useQuery({
    queryKey: ['marketAnalytics', analyticsParams],
    queryFn: () => getMarketAnalytics(analyticsParams).then(r => r.data),
    refetchInterval: 60000
  })

  // 4. Fetch Paginated Raw Listings
  const { data: listingsData = { items: [], total: 0, total_pages: 1 } } = useQuery({
    queryKey: ['marketListings', rawPage, selectedProduct, selectedCondition],
    queryFn: () => getMarketListings({
      page: rawPage,
      page_size: 10,
      product_id: selectedProduct ? Number(selectedProduct) : undefined,
      condition_id: selectedCondition ? Number(selectedCondition) : undefined
    }).then(r => r.data)
  })

  // 5. Fetch Quality and Operations
  const { data: qualityData = null } = useQuery({
    queryKey: ['marketQuality'],
    queryFn: () => getMarketQuality().then(r => r.data),
    refetchInterval: 30000
  })

  // Preset button: iPhone 16 / 128GB / New Sealed
  const applyPresetIPhone16 = () => {
    setSelectedProduct('1')
    setSelectedVariant('1')
    setSelectedCondition('1')
  }

  const overview = analytics?.overview || {}
  const histogram = analytics?.histogram || []
  const sources = analytics?.source_comparison || []
  const trends = analytics?.trend_history || []

  return (
    <Box bg="gray.50" minH="calc(100vh - 60px)" py={6}>
      <Container maxW="7xl">
        {/* Header Bar */}
        <Flex justify="space-between" align="center" mb={6} flexWrap="wrap" gap={4}>
          <Box>
            <HStack spacing={3}>
              <Heading size="lg" color="gray.800">Market Price Intelligence</Heading>
              <Badge colorScheme="purple" fontSize="0.8em" px={2} py={0.5} borderRadius="md">
                Phase 4 Realtime
              </Badge>
            </HStack>
            <Text color="gray.500" fontSize="sm" mt={1}>
              Deep analytics, multi-source price discovery & fair market valuation
            </Text>
          </Box>
          <HStack spacing={3}>
            <Button
              size="sm"
              colorScheme="blue"
              variant="outline"
              leftIcon={<Smartphone size={16} />}
              onClick={applyPresetIPhone16}
            >
              Preset: iPhone 16 / 128GB / New Sealed
            </Button>
            <Button
              size="sm"
              leftIcon={<RefreshCw size={14} />}
              onClick={() => refetchAnalytics()}
              isLoading={loadingAnalytics}
            >
              Refresh
            </Button>
          </HStack>
        </Flex>

        {/* Global Filter Bar */}
        <Card mb={6} shadow="sm" borderRadius="lg" bg="white">
          <CardBody py={4}>
            <SimpleGrid columns={{ base: 1, sm: 2, md: 5 }} spacing={4}>
              <Box>
                <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>DANH MỤC</Text>
                <Select
                  size="sm"
                  borderRadius="md"
                  placeholder="Tất cả danh mục"
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                >
                  {explorerData.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </Select>
              </Box>

              <Box>
                <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>SẢN PHẨM (CANONICAL)</Text>
                <Select
                  size="sm"
                  borderRadius="md"
                  value={selectedProduct}
                  onChange={(e) => setSelectedProduct(e.target.value)}
                >
                  <option value="">Tất cả sản phẩm</option>
                  <option value="1">iPhone 16</option>
                  <option value="2">MSI GeForce RTX 4060</option>
                  <option value="3">Samsung Server RAM</option>
                </Select>
              </Box>

              <Box>
                <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>BIẾN THỂ (VARIANT)</Text>
                <Select
                  size="sm"
                  borderRadius="md"
                  value={selectedVariant}
                  onChange={(e) => setSelectedVariant(e.target.value)}
                >
                  <option value="">Tất cả biến thể</option>
                  <option value="1">128GB Black</option>
                  <option value="2">256GB Desert Titanium</option>
                </Select>
              </Box>

              <Box>
                <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>TÌNH TRẠNG (CONDITION)</Text>
                <Select
                  size="sm"
                  borderRadius="md"
                  value={selectedCondition}
                  onChange={(e) => setSelectedCondition(e.target.value)}
                >
                  <option value="">Tất cả tình trạng</option>
                  {conditionsData.map(c => (
                    <option key={c.id} value={c.id}>{c.code} - {c.name}</option>
                  ))}
                </Select>
              </Box>

              <Box>
                <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>KHOẢNG THỜI GIAN</Text>
                <Select
                  size="sm"
                  borderRadius="md"
                  value={timeframeDays}
                  onChange={(e) => setTimeframeDays(Number(e.target.value))}
                >
                  <option value={7}>7 ngày qua</option>
                  <option value={30}>30 ngày qua</option>
                  <option value={90}>90 ngày qua</option>
                </Select>
              </Box>
            </SimpleGrid>
          </CardBody>
        </Card>

        {/* 7 Screens / Sub-Tabs */}
        <Tabs variant="enclosed" colorScheme="blue">
          <TabList bg="white" p={2} borderRadius="md" shadow="xs" flexWrap="wrap">
            <Tab fontWeight="semibold"><Activity size={16} style={{ marginRight: 6 }} /> 1. Market Overview</Tab>
            <Tab fontWeight="semibold"><BarChart3 size={16} style={{ marginRight: 6 }} /> 2. Price Distribution</Tab>
            <Tab fontWeight="semibold"><Layers size={16} style={{ marginRight: 6 }} /> 3. Source Comparison</Tab>
            <Tab fontWeight="semibold"><TrendingUp size={16} style={{ marginRight: 6 }} /> 4. Price Trend</Tab>
            <Tab fontWeight="semibold"><Database size={16} style={{ marginRight: 6 }} /> 5. Raw Evidence</Tab>
            <Tab fontWeight="semibold"><Search size={16} style={{ marginRight: 6 }} /> 6. Product Explorer</Tab>
            <Tab fontWeight="semibold"><ShieldCheck size={16} style={{ marginRight: 6 }} /> 7. Data Quality & Ops</Tab>
          </TabList>

          <TabPanels mt={4}>
            {/* SCREEN 1: MARKET OVERVIEW */}
            <TabPanel p={0}>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4} mb={6}>
                <Card shadow="sm" borderRadius="lg">
                  <CardBody>
                    <Stat>
                      <StatLabel color="gray.500">Fair Market Price (Giá thị trường chuẩn)</StatLabel>
                      <StatNumber fontSize="2xl" color="blue.600">{FORMAT_CURRENCY(overview.fair_price)}</StatNumber>
                      <StatHelpText>
                        <StatArrow type={overview.trend_percentage >= 0 ? "increase" : "decrease"} />
                        {overview.trend_percentage}% trong {timeframeDays} ngày
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card shadow="sm" borderRadius="lg">
                  <CardBody>
                    <Stat>
                      <StatLabel color="gray.500">Quick Sell Price (Giá xả nhanh 24-48h)</StatLabel>
                      <StatNumber fontSize="2xl" color="green.600">{FORMAT_CURRENCY(overview.quick_sell_price)}</StatNumber>
                      <StatHelpText color="gray.500">~ P15-P20 liquidation target</StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card shadow="sm" borderRadius="lg">
                  <CardBody>
                    <Stat>
                      <StatLabel color="gray.500">Market Confidence (Độ tin cậy)</StatLabel>
                      <StatNumber fontSize="2xl" color="purple.600">{overview.confidence || 90}%</StatNumber>
                      <Progress value={overview.confidence || 90} size="xs" colorScheme="purple" mt={2} borderRadius="full" />
                    </Stat>
                  </CardBody>
                </Card>

                <Card shadow="sm" borderRadius="lg">
                  <CardBody>
                    <Stat>
                      <StatLabel color="gray.500">Liquidity (Tính thanh khoản)</StatLabel>
                      <StatNumber fontSize="2xl" color="orange.500">{overview.liquidity || 85} / 100</StatNumber>
                      <Progress value={overview.liquidity || 85} size="xs" colorScheme="orange" mt={2} borderRadius="full" />
                    </Stat>
                  </CardBody>
                </Card>
              </SimpleGrid>

              {/* Percentiles Breakdown Table */}
              <Card shadow="sm" borderRadius="lg" bg="white">
                <CardHeader pb={2}>
                  <Heading size="md" color="gray.700">Percentile Distribution & Valuation Metrics</Heading>
                </CardHeader>
                <CardBody>
                  <SimpleGrid columns={{ base: 2, sm: 3, md: 6 }} spacing={4}>
                    <Box p={3} bg="gray.50" borderRadius="md" textAlign="center">
                      <Text fontSize="xs" color="gray.500" fontWeight="bold">MẪU DỮ LIỆU</Text>
                      <Text fontSize="xl" fontWeight="bold" color="gray.700">{overview.samples || 0}</Text>
                      <Text fontSize="xs" color="gray.400">({overview.outliers_count || 0} outliers)</Text>
                    </Box>
                    <Box p={3} bg="blue.50" borderRadius="md" textAlign="center">
                      <Text fontSize="xs" color="blue.600" fontWeight="bold">P10 (Rất rẻ)</Text>
                      <Text fontSize="md" fontWeight="bold" color="blue.700">{FORMAT_CURRENCY(overview.p10)}</Text>
                    </Box>
                    <Box p={3} bg="blue.50" borderRadius="md" textAlign="center">
                      <Text fontSize="xs" color="blue.600" fontWeight="bold">P25 (Rẻ)</Text>
                      <Text fontSize="md" fontWeight="bold" color="blue.700">{FORMAT_CURRENCY(overview.p25)}</Text>
                    </Box>
                    <Box p={3} bg="green.50" borderRadius="md" textAlign="center" border="1px solid" borderColor="green.200">
                      <Text fontSize="xs" color="green.700" fontWeight="bold">MEDIAN (P50)</Text>
                      <Text fontSize="md" fontWeight="bold" color="green.800">{FORMAT_CURRENCY(overview.median)}</Text>
                    </Box>
                    <Box p={3} bg="orange.50" borderRadius="md" textAlign="center">
                      <Text fontSize="xs" color="orange.600" fontWeight="bold">P75 (Cao)</Text>
                      <Text fontSize="md" fontWeight="bold" color="orange.700">{FORMAT_CURRENCY(overview.p75)}</Text>
                    </Box>
                    <Box p={3} bg="red.50" borderRadius="md" textAlign="center">
                      <Text fontSize="xs" color="red.600" fontWeight="bold">P90 (Rất cao)</Text>
                      <Text fontSize="md" fontWeight="bold" color="red.700">{FORMAT_CURRENCY(overview.p90)}</Text>
                    </Box>
                  </SimpleGrid>
                </CardBody>
              </Card>
            </TabPanel>

            {/* SCREEN 2: PRICE DISTRIBUTION */}
            <TabPanel p={0}>
              <Card shadow="sm" borderRadius="lg" bg="white">
                <CardHeader>
                  <Flex justify="space-between" align="center" flexWrap="wrap" gap={2}>
                    <Box>
                      <Heading size="md" color="gray.700">Price Distribution Histogram</Heading>
                      <Text fontSize="sm" color="gray.500">Số lượng tin đăng theo phân khúc giá (Price Buckets)</Text>
                    </Box>
                    <Select
                      size="sm"
                      w="220px"
                      placeholder="Tất cả nguồn"
                      value={distributionSource}
                      onChange={(e) => setDistributionSource(e.target.value)}
                    >
                      <option value="11">Chợ Tốt</option>
                      <option value="12">Facebook Marketplace</option>
                      <option value="13">Facebook Groups</option>
                      <option value="10">Goofish (闲鱼)</option>
                    </Select>
                  </Flex>
                </CardHeader>
                <CardBody h="400px">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={histogram} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="label" stroke="#718096" fontSize={12} />
                      <YAxis stroke="#718096" fontSize={12} allowDecimals={false} />
                      <RechartsTooltip formatter={(val) => [`${val} tin đăng`, 'Số lượng']} />
                      <Bar dataKey="count" fill="#3182CE" radius={[4, 4, 0, 0]} name="Số lượng tin đăng" />
                    </BarChart>
                  </ResponsiveContainer>
                </CardBody>
              </Card>
            </TabPanel>

            {/* SCREEN 3: SOURCE COMPARISON */}
            <TabPanel p={0}>
              <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
                <Card shadow="sm" borderRadius="lg" bg="white">
                  <CardHeader>
                    <Heading size="md" color="gray.700">Source Price Metrics</Heading>
                    <Text fontSize="sm" color="gray.500">So sánh mức giá P25, Median, P75 giữa các nền tảng</Text>
                  </CardHeader>
                  <CardBody p={0}>
                    <Table size="sm" variant="simple">
                      <Thead bg="gray.50">
                        <Tr>
                          <Th>Nguồn</Th>
                          <Th isNumeric>Số tin</Th>
                          <Th isNumeric>P25</Th>
                          <Th isNumeric>Median</Th>
                          <Th isNumeric>P75</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {sources.map((s, idx) => (
                          <Tr key={idx}>
                            <Td fontWeight="bold">{s.source}</Td>
                            <Td isNumeric><Tag size="sm">{s.samples}</Tag></Td>
                            <Td isNumeric>{FORMAT_CURRENCY(s.p25)}</Td>
                            <Td isNumeric fontWeight="bold" color="blue.600">{FORMAT_CURRENCY(s.median)}</Td>
                            <Td isNumeric>{FORMAT_CURRENCY(s.p75)}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </CardBody>
                </Card>

                <Card shadow="sm" borderRadius="lg" bg="white">
                  <CardHeader>
                    <Heading size="md" color="gray.700">Median Price by Source</Heading>
                    <Text fontSize="sm" color="gray.500">Mức giá trung vị đối chiếu giữa các chợ</Text>
                  </CardHeader>
                  <CardBody h="340px">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={sources} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="source" stroke="#718096" fontSize={11} />
                        <YAxis stroke="#718096" fontSize={11} tickFormatter={(v) => `${(v/1000000).toFixed(1)}M`} />
                        <RechartsTooltip formatter={(val) => [FORMAT_CURRENCY(val), 'Giá trung vị']} />
                        <Bar dataKey="median" fill="#38A169" radius={[4, 4, 0, 0]} name="Median" />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardBody>
                </Card>
              </SimpleGrid>
            </TabPanel>

            {/* SCREEN 4: TREND */}
            <TabPanel p={0}>
              <Card shadow="sm" borderRadius="lg" bg="white">
                <CardHeader>
                  <Flex justify="space-between" align="center" flexWrap="wrap" gap={2}>
                    <Box>
                      <Heading size="md" color="gray.700">Historical Price Trend</Heading>
                      <Text fontSize="sm" color="gray.500">Biến động giá qua thời gian: P25, Median, P75 và Quick Sell</Text>
                    </Box>
                    <HStack spacing={2}>
                      {[7, 30, 90].map(d => (
                        <Button
                          key={d}
                          size="xs"
                          colorScheme={timeframeDays === d ? "blue" : "gray"}
                          onClick={() => setTimeframeDays(d)}
                        >
                          {d}d
                        </Button>
                      ))}
                    </HStack>
                  </Flex>
                </CardHeader>
                <CardBody h="400px">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trends} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" stroke="#718096" fontSize={12} />
                      <YAxis stroke="#718096" fontSize={12} tickFormatter={(v) => `${(v/1000000).toFixed(1)}M`} />
                      <RechartsTooltip formatter={(val) => [FORMAT_CURRENCY(val)]} />
                      <Legend />
                      <Line type="monotone" dataKey="p75" stroke="#E53E3E" strokeDasharray="4 4" name="P75 (Cao)" />
                      <Line type="monotone" dataKey="median" stroke="#3182CE" strokeWidth={3} name="Median (Trung vị)" />
                      <Line type="monotone" dataKey="p25" stroke="#38A169" strokeDasharray="4 4" name="P25 (Rẻ)" />
                      <Line type="monotone" dataKey="quick_sell" stroke="#DD6B20" strokeWidth={2} name="Quick Sell" />
                    </LineChart>
                  </ResponsiveContainer>
                </CardBody>
              </Card>
            </TabPanel>

            {/* SCREEN 5: RAW LISTINGS EVIDENCE */}
            <TabPanel p={0}>
              <Card shadow="sm" borderRadius="lg" bg="white">
                <CardHeader>
                  <Heading size="md" color="gray.700">Raw Market Evidence Listings</Heading>
                  <Text fontSize="sm" color="gray.500">Dữ liệu tin đăng thực tế thu thập từ các sàn</Text>
                </CardHeader>
                <CardBody p={0}>
                  <Box overflowX="auto">
                    <Table size="sm" variant="simple">
                      <Thead bg="gray.50">
                        <Tr>
                          <Th>Nguồn</Th>
                          <Th>Tiêu đề tin đăng</Th>
                          <Th>Sản phẩm chuẩn</Th>
                          <Th>Tình trạng</Th>
                          <Th isNumeric>Giá</Th>
                          <Th>Cập nhật</Th>
                          <Th>Trạng thái</Th>
                          <Th>Link gốc</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {listingsData.items.map((row) => (
                          <Tr key={row.id}>
                            <Td><Badge colorScheme="blue">{row.source_name}</Badge></Td>
                            <Td maxW="280px" isTruncated title={row.raw_title}>{row.raw_title}</Td>
                            <Td fontWeight="semibold">{row.normalized_product}</Td>
                            <Td><Tag size="sm" colorScheme="purple">{row.condition_code}</Tag></Td>
                            <Td isNumeric fontWeight="bold" color="blue.700">{FORMAT_CURRENCY(row.price)}</Td>
                            <Td fontSize="xs" color="gray.500">
                              {row.last_seen ? new Date(row.last_seen).toLocaleDateString('vi-VN') : '—'}
                            </Td>
                            <Td>
                              <Badge colorScheme={row.status === 'VALID' ? 'green' : 'red'}>
                                {row.status}
                              </Badge>
                            </Td>
                            <Td>
                              {row.url ? (
                                <ChakraLink href={row.url} isExternal color="blue.500">
                                  <ExternalLink size={14} />
                                </ChakraLink>
                              ) : '—'}
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                  {/* Pagination Controls */}
                  <Flex justify="space-between" align="center" px={4} py={3} borderTop="1px solid" borderColor="gray.100">
                    <Text fontSize="sm" color="gray.500">
                      Trang {listingsData.page} / {listingsData.total_pages} (Tổng {listingsData.total} tin đăng)
                    </Text>
                    <HStack spacing={2}>
                      <IconButton
                        size="sm"
                        icon={<ChevronLeft size={16} />}
                        isDisabled={rawPage <= 1}
                        onClick={() => setRawPage(p => Math.max(1, p - 1))}
                        aria-label="Previous page"
                      />
                      <IconButton
                        size="sm"
                        icon={<ChevronRight size={16} />}
                        isDisabled={rawPage >= listingsData.total_pages}
                        onClick={() => setRawPage(p => p + 1)}
                        aria-label="Next page"
                      />
                    </HStack>
                  </Flex>
                </CardBody>
              </Card>
            </TabPanel>

            {/* SCREEN 6: PRODUCT EXPLORER */}
            <TabPanel p={0}>
              <Card shadow="sm" borderRadius="lg" bg="white">
                <CardHeader>
                  <Heading size="md" color="gray.700">Taxonomy Product Explorer</Heading>
                  <Text fontSize="sm" color="gray.500">Cây phân cấp: Danh mục → Thương hiệu → Dòng sản phẩm → Biến thể</Text>
                </CardHeader>
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    {explorerData.map(cat => (
                      <Box key={cat.id} p={4} borderWidth="1px" borderRadius="md" bg="gray.50">
                        <Heading size="sm" color="blue.700" mb={3}>📂 {cat.name}</Heading>
                        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                          {cat.brands?.map(b => (
                            <Box key={b.id} p={3} bg="white" borderRadius="md" shadow="xs">
                              <Text fontWeight="bold" color="gray.800" mb={2}>🏷️ {b.name}</Text>
                              {b.products?.map(p => (
                                <Box key={p.id} pl={2} mb={2} borderLeft="2px solid" borderColor="blue.300">
                                  <Text fontSize="sm" fontWeight="semibold" color="gray.700">{p.name}</Text>
                                  <Text fontSize="xs" color="gray.500">Model: {p.model_code || 'N/A'}</Text>
                                  <HStack spacing={1} mt={1} flexWrap="wrap">
                                    {p.variants?.map(v => (
                                      <Tag
                                        key={v.id}
                                        size="sm"
                                        cursor="pointer"
                                        colorScheme="blue"
                                        onClick={() => {
                                          setSelectedProduct(String(p.id))
                                          setSelectedVariant(String(v.id))
                                        }}
                                      >
                                        {v.name}
                                      </Tag>
                                    ))}
                                  </HStack>
                                </Box>
                              ))}
                            </Box>
                          ))}
                        </SimpleGrid>
                      </Box>
                    ))}
                  </VStack>
                </CardBody>
              </Card>
            </TabPanel>

            {/* SCREEN 7: DATA QUALITY & OPERATIONS */}
            <TabPanel p={0}>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4} mb={6}>
                <Card shadow="sm" borderRadius="lg">
                  <CardBody>
                    <Stat>
                      <StatLabel color="gray.500">Review Queue (Cần duyệt)</StatLabel>
                      <StatNumber fontSize="2xl" color="orange.500">{qualityData?.review_queue || 0}</StatNumber>
                      <StatHelpText>Tin đăng độ tin cậy thấp</StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card shadow="sm" borderRadius="lg">
                  <CardBody>
                    <Stat>
                      <StatLabel color="gray.500">Invalid Prices (Giá ảo đã lọc)</StatLabel>
                      <StatNumber fontSize="2xl" color="red.500">{qualityData?.invalid_prices || 0}</StatNumber>
                      <StatHelpText>Dummy, inbox, teaser</StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card shadow="sm" borderRadius="lg">
                  <CardBody>
                    <Stat>
                      <StatLabel color="gray.500">Outliers Filtered (Giá ngoại lai)</StatLabel>
                      <StatNumber fontSize="2xl" color="blue.500">{qualityData?.outliers_filtered || 0}</StatNumber>
                      <StatHelpText>Loại bỏ bởi thuật toán IQR</StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card shadow="sm" borderRadius="lg">
                  <CardBody>
                    <Stat>
                      <StatLabel color="gray.500">Overall Confidence</StatLabel>
                      <StatNumber fontSize="2xl" color="green.600">{qualityData?.overall_market_confidence || 92}%</StatNumber>
                      <StatHelpText>Chất lượng dữ liệu tổng thể</StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>
              </SimpleGrid>

              {/* Collector Statuses Table */}
              <Card shadow="sm" borderRadius="lg" bg="white">
                <CardHeader>
                  <Heading size="md" color="gray.700">Collector Scanning & Authentication Status</Heading>
                  <Text fontSize="sm" color="gray.500">Tình trạng vận hành thời gian thực của các bộ cào dữ liệu</Text>
                </CardHeader>
                <CardBody p={0}>
                  <Table size="sm" variant="simple">
                    <Thead bg="gray.50">
                      <Tr>
                        <Th>Nền tảng</Th>
                        <Th>Trạng thái</Th>
                        <Th>Xác thực (Auth Status)</Th>
                        <Th isNumeric>Số tin quét</Th>
                        <Th>Lần quét gần nhất</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {qualityData?.collectors?.map((c, idx) => (
                        <Tr key={idx}>
                          <Td fontWeight="bold">{c.source}</Td>
                          <Td>
                            <Badge colorScheme={c.status === 'SUCCESS' ? 'green' : (c.status === 'RUNNING' ? 'blue' : 'red')}>
                              {c.status}
                            </Badge>
                          </Td>
                          <Td>
                            <Tag size="sm" colorScheme={c.auth_status === 'OK' ? 'green' : 'orange'}>
                              {c.auth_status}
                            </Tag>
                          </Td>
                          <Td isNumeric>{c.items_scanned}</Td>
                          <Td fontSize="xs" color="gray.500">
                            {c.last_start ? new Date(c.last_start).toLocaleString('vi-VN') : '—'}
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </CardBody>
              </Card>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </Container>
    </Box>
  )
}
