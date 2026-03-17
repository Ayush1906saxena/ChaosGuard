package com.chaosguard.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.serializer.JsonSerializer;

import java.util.HashMap;
import java.util.Map;

@Configuration
public class KafkaConfig {

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    @Value("${chaosguard.kafka.topics.repo-clone-events}")
    private String repoCloneEventsTopic;

    @Value("${chaosguard.kafka.topics.index-events}")
    private String indexEventsTopic;

    @Value("${chaosguard.kafka.topics.scan-progress}")
    private String scanProgressTopic;

    @Value("${chaosguard.kafka.topics.scan-complete}")
    private String scanCompleteTopic;

    @Value("${chaosguard.kafka.topics.results-ready}")
    private String resultsReadyTopic;

    @Value("${chaosguard.kafka.topics.analysis-events}")
    private String analysisEventsTopic;

    @Value("${chaosguard.kafka.topics.scan-recon-events}")
    private String scanReconEventsTopic;

    @Value("${chaosguard.kafka.topics.scan-hunter-events}")
    private String scanHunterEventsTopic;

    @Value("${chaosguard.kafka.topics.scan-siege-events}")
    private String scanSiegeEventsTopic;

    @Bean
    public NewTopic repoCloneEventsTopic() {
        return TopicBuilder.name(repoCloneEventsTopic)
                .partitions(6)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic indexEventsTopic() {
        return TopicBuilder.name(indexEventsTopic)
                .partitions(6)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic scanProgressTopic() {
        return TopicBuilder.name(scanProgressTopic)
                .partitions(3)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic scanCompleteTopic() {
        return TopicBuilder.name(scanCompleteTopic)
                .partitions(3)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic resultsReadyTopic() {
        return TopicBuilder.name(resultsReadyTopic)
                .partitions(3)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic analysisEventsTopic() {
        return TopicBuilder.name(analysisEventsTopic)
                .partitions(6)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic scanReconEventsTopic() {
        return TopicBuilder.name(scanReconEventsTopic)
                .partitions(6)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic scanHunterEventsTopic() {
        return TopicBuilder.name(scanHunterEventsTopic)
                .partitions(6)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic scanSiegeEventsTopic() {
        return TopicBuilder.name(scanSiegeEventsTopic)
                .partitions(6)
                .replicas(1)
                .build();
    }

    @Bean
    public ProducerFactory<String, Object> producerFactory() {
        Map<String, Object> configProps = new HashMap<>();
        configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        configProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        configProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class);
        configProps.put(ProducerConfig.ACKS_CONFIG, "all");
        configProps.put(ProducerConfig.RETRIES_CONFIG, 3);
        configProps.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        configProps.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 1);
        return new DefaultKafkaProducerFactory<>(configProps);
    }

    @Bean
    public KafkaTemplate<String, Object> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }
}
