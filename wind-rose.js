// Wonky Prototype from Claude. Put into a React project to get it working.

import React, { useState } from 'react';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, 
         Radar, Tooltip } from 'recharts';

const FilledWindRose = () => {
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const speedBins = ['0-2', '2-4', '4-6', '6-8', '8-10', '10-12', '12-14', '14-16', '16-18'];
    
    const colorScales = {
        '850mb': {
            name: '850mb (~1500m)',
            colors: [
                'rgba(230, 240, 255, 0.6)',
                'rgba(200, 220, 255, 0.6)',
                'rgba(170, 200, 255, 0.6)',
                'rgba(140, 180, 255, 0.6)',
                'rgba(110, 160, 255, 0.6)',
                'rgba(80, 140, 255, 0.6)',
                'rgba(50, 120, 255, 0.6)',
                'rgba(20, 100, 255, 0.6)',
                'rgba(0, 80, 255, 0.6)'
            ],
            blendMode: 'normal'
        },
        '925mb': {
            name: '925mb (~750m)',
            colors: [
                'rgba(255, 230, 255, 0.5)',
                'rgba(255, 200, 255, 0.5)',
                'rgba(255, 170, 255, 0.5)',
                'rgba(255, 140, 255, 0.5)',
                'rgba(255, 110, 255, 0.5)',
                'rgba(255, 80, 255, 0.5)',
                'rgba(255, 50, 255, 0.5)',
                'rgba(255, 20, 255, 0.5)',
                'rgba(255, 0, 255, 0.5)'
            ],
            blendMode: 'normal'
        },
        '10m': {
            name: '10m (Surface)',
            colors: [
                'rgba(255, 255, 230, 0.4)',
                'rgba(255, 255, 200, 0.4)',
                'rgba(255, 255, 170, 0.4)',
                'rgba(255, 255, 140, 0.4)',
                'rgba(255, 255, 110, 0.4)',
                'rgba(255, 255, 80, 0.4)',
                'rgba(255, 255, 50, 0.4)',
                'rgba(255, 255, 20, 0.4)',
                'rgba(255, 255, 0, 0.4)'
            ],
            blendMode: 'normal'
        }
    };

    const [visibleLayers, setVisibleLayers] = useState({
        '850mb': true,
        '925mb': true,
        '10m': true
    });

    // Modified data generation to create cumulative values for filled sectors
    const generateData = () => {
        return directions.map(dir => {
            // Generate base values
            const baseValues = Object.keys(colorScales).reduce((acc, height) => ({
                ...acc,
                [height]: speedBins.map(() => Math.floor(Math.random() * 10))
            }), {});

            // Create cumulative values for each height
            return {
                direction: dir,
                ...Object.keys(colorScales).reduce((acc, height) => ({
                    ...acc,
                    [height]: speedBins.map((_, index) => ({
                        speed: speedBins[index],
                        // Cumulative sum up to this speed bin
                        value: baseValues[height].slice(0, index + 1)
                            .reduce((sum, val) => sum + val, 0)
                    }))
                }), {})
            };
        });
    };

    const [data] = useState(generateData());

    const CustomTooltip = ({ active, payload }) => {
        if (active && payload && payload.length) {
            const direction = payload[0].payload.direction;
            return (
                <div className="bg-white p-4 border border-gray-200 rounded shadow-lg">
                    <h4 className="font-semibold text-lg mb-2">{direction}</h4>
                    {Object.keys(colorScales)
                        .filter(height => visibleLayers[height])
                        .map(height => {
                            const heightData = payload[0].payload[height];
                            // Calculate individual bin values from cumulative
                            const binValues = heightData.map((bin, i) => ({
                                speed: bin.speed,
                                value: bin.value - (i > 0 ? heightData[i-1].value : 0)
                            })).filter(bin => bin.value > 0);

                            if (binValues.length === 0) return null;
                            
                            return (
                                <div key={height} className="mb-3">
                                    <p className="font-medium text-sm text-gray-700">
                                        {colorScales[height].name}
                                    </p>
                                    <div className="ml-2">
                                        {binValues.map(bin => (
                                            <p key={bin.speed} className="text-sm text-gray-600">
                                                {`${bin.speed} km/h: ${bin.value}`}
                                            </p>
                                        ))}
                                    </div>
                                </div>
                            );
                        })}
                </div>
            );
        }
        return null;
    };

    return (
        <div className="w-full h-full bg-white p-6">
            <div className="grid grid-cols-4 gap-6">
                <div className="col-span-3 h-96 bg-white">
                    <ResponsiveContainer>
                        <RadarChart data={data}>
                            <PolarGrid gridType="circle" />
                            <PolarAngleAxis 
                                dataKey="direction"
                                tick={{ fill: '#374151', fontSize: 14 }}
                            />
                            
                            {Object.keys(colorScales)
                                .filter(height => visibleLayers[height])
                                .reverse()
                                .map((height) => (
                                    // Create filled sectors for each speed bin
                                    speedBins.map((_, speedIndex) => (
                                        <Radar
                                            key={`${height}-${speedIndex}`}
                                            name={`${speedBins[speedIndex]} km/h`}
                                            dataKey={entry => entry[height][speedIndex].value}
                                            stroke="none"
                                            fill={colorScales[height].colors[speedIndex]}
                                            style={{ mixBlendMode: colorScales[height].blendMode }}
                                        />
                                    ))
                            ))}
                            <Tooltip content={<CustomTooltip />} />
                        </RadarChart>
                    </ResponsiveContainer>
                </div>

                <div className="space-y-6">
                    {Object.entries(colorScales).map(([height, scale]) => (
                        <button
                            key={height}
                            onClick={() => setVisibleLayers(prev => ({
                                ...prev,
                                [height]: !prev[height]
                            }))}
                            className={`w-full bg-gray-50 p-4 rounded-lg transition-opacity ${
                                visibleLayers[height] ? 'opacity-100' : 'opacity-50'
                            }`}
                        >
                            <h3 className="font-semibold text-sm mb-2">{scale.name}</h3>
                            <div className="grid grid-cols-9 gap-1">
                                {scale.colors.map((color, i) => (
                                    <div
                                        key={i}
                                        className="aspect-square rounded"
                                        style={{ backgroundColor: color }}
                                    />
                                ))}
                            </div>
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default FilledWindRose;